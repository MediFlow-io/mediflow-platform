<?php

namespace Tests\Feature;

use App\Services\MediflowClient;
use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

class SettingsTest extends TestCase
{
    private const API = 'http://api.test';

    protected function setUp(): void
    {
        parent::setUp();
        config(['mediflow.gateway_url' => 'http://gateway.test', 'mediflow.api_url' => self::API, 'mediflow.flow_url' => 'http://flow.test']);
    }

    private function signedIn(): self
    {
        return $this->withSession([MediflowClient::SESSION_KEY => [
            'access' => 'ACCESS-1', 'refresh' => 'REFRESH-1', 'user' => ['id' => 1, 'username' => 'admin', 'name' => 'Ada Admin'],
        ]]);
    }

    private function queue(): array
    {
        return ['esi1_target_minutes' => 0, 'esi2_target_minutes' => 10, 'esi3_target_minutes' => 30, 'esi4_target_minutes' => 60,
            'esi5_target_minutes' => 120, 'long_wait_minutes' => 60, 'turn_near_ahead' => 2, 'slot_minutes' => 15,
            'max_days_ahead' => 60, 'min_notice_minutes' => 15, 'max_open_appointments' => 3, 'updated_at' => '2026-10-19T10:00:00Z'];
    }

    public function test_guests_cannot_reach_settings(): void
    {
        foreach (['/settings', '/settings/hours', '/settings/rota'] as $path) {
            $this->get($path)->assertRedirect('/login');
        }
    }

    public function test_queue_rules_and_holidays(): void
    {
        Http::fake([
            self::API.'/api/clinic/queue-settings' => Http::response($this->queue()),
            self::API.'/api/clinic/holidays?upcoming=1' => Http::response([['id' => 4, 'date' => '2026-12-25', 'name' => 'Christmas Day']]),
            self::API.'/api/clinic/holidays' => Http::response(['id' => 5, 'date' => '2026-12-26', 'name' => 'Boxing Day'], 201),
            self::API.'/api/clinic/holidays/4' => Http::response(null, 204),
        ]);
        $this->signedIn()->get('/settings')->assertOk()->assertSee('Christmas Day')->assertSee('Fri 25 Dec 2026')
            ->assertSee('value="10"', false);

        $form = array_map('strval', array_diff_key($this->queue(), ['updated_at' => 1])) + ['long_wait_minutes' => '45'];
        $form['long_wait_minutes'] = '45';
        $this->signedIn()->post('/settings/queue', $form)->assertRedirect('/settings')->assertSessionHas('status', 'Queue rules saved.');
        Http::assertSent(fn (Request $r) => $r->method() === 'PUT' && $r['long_wait_minutes'] === 45 && $r['esi2_target_minutes'] === 10);

        $this->signedIn()->post('/settings/queue', ['slot_minutes' => 7] + $form)->assertSessionHasErrors('slot_minutes');

        $this->signedIn()->post('/settings/holidays', ['date' => '2026-12-26', 'name' => 'Boxing Day'])
            ->assertSessionHas('status', 'Holiday added: Boxing Day (2026-12-26). No appointments can be booked that day.');
        $this->signedIn()->post('/settings/holidays', ['date' => '2001-01-01', 'name' => 'Past'])->assertSessionHasErrors('date');
        $this->signedIn()->delete('/settings/holidays/4')->assertSessionHas('status', 'Holiday removed.');
        Http::assertSent(fn (Request $r) => $r->method() === 'DELETE' && str_ends_with($r->url(), '/api/clinic/holidays/4'));
    }

    public function test_opening_hours_per_department(): void
    {
        Http::fake([
            self::API.'/api/departments' => Http::response([['id' => 1, 'name' => 'Outpatient', 'code' => 'opd', 'active' => true]]),
            self::API.'/api/clinic/hours' => Http::sequence()
                ->push([['department' => null, 'weekday' => 1, 'day' => 'Mon', 'opens' => '08:00:00', 'closes' => '16:00:00']])
                ->push([['department' => null, 'weekday' => 1, 'day' => 'Mon', 'opens' => '08:00:00', 'closes' => '16:00:00']])
                ->push([]),
        ]);
        $this->signedIn()->get('/settings/hours')->assertOk()->assertSee('value="08:00"', false);
        $this->signedIn()->get('/settings/hours?department=1')->assertOk()->assertSee('This department uses the clinic default hours.');

        $this->signedIn()->post('/settings/hours', ['department' => 1, 'days' => [
            5 => ['open' => '1', 'opens' => '08:00', 'closes' => '12:00'],
            6 => ['opens' => '09:00', 'closes' => '10:00'], // not ticked: closed
        ]])->assertRedirect('/settings/hours?department=1')->assertSessionHas('status', 'Opening hours saved.');
        Http::assertSent(fn (Request $r) => $r->method() === 'PUT' && $r['department'] === 1
            && $r['days'] === [['weekday' => 5, 'opens' => '08:00', 'closes' => '12:00']]);

        $this->signedIn()->post('/settings/hours', ['department' => 1, 'days' => [1 => ['open' => '1', 'opens' => '16:00', 'closes' => '08:00']]])
            ->assertSessionHasErrors('days.1');
    }

    public function test_rota_adds_one_shift_per_ticked_day(): void
    {
        Http::fake([
            self::API.'/api/clinic/shifts' => Http::response(['id' => 1], 201),
            self::API.'/api/clinic/shifts/9' => Http::response(null, 204),
        ]);
        $this->signedIn()->post('/settings/rota', ['user' => 2, 'department' => 1, 'weekdays' => [1, 3, 3], 'starts' => '08:00', 'ends' => '14:00'])
            ->assertRedirect('/settings/rota')->assertSessionHas('status', '2 shifts added.');
        Http::assertSentCount(2);
        Http::assertSent(fn (Request $r) => $r['weekday'] === 3 && $r['user'] === 2 && $r['ends'] === '14:00');

        $this->signedIn()->post('/settings/rota', ['user' => 2, 'department' => 1, 'weekdays' => [1], 'starts' => '14:00', 'ends' => '08:00'])
            ->assertSessionHasErrors(['ends' => 'The shift must end after it starts.']);
        $this->signedIn()->delete('/settings/rota/9')->assertSessionHas('status', 'Shift removed.');
    }

    public function test_rota_page_lists_staff_but_not_students(): void
    {
        Http::fake([
            self::API.'/api/clinic/shifts' => Http::response([['id' => 9, 'user' => 2, 'user_name' => 'Dr Demo', 'role' => 'doctor',
                'department' => 1, 'department_name' => 'Outpatient', 'weekday' => 1, 'day' => 'Mon', 'starts' => '08:00:00', 'ends' => '14:00:00']]),
            self::API.'/api/users*' => Http::response([
                ['id' => 2, 'username' => 'doctor', 'display_name' => 'Dr Demo', 'role' => 'doctor'],
                ['id' => 3, 'username' => 'E2E/1', 'display_name' => 'A Student', 'role' => 'student'],
            ]),
            self::API.'/api/departments' => Http::response([['id' => 1, 'name' => 'Outpatient', 'code' => 'opd', 'active' => true]]),
        ]);
        $this->signedIn()->get('/settings/rota')->assertOk()->assertSee('Dr Demo (doctor)')->assertDontSee('A Student')
            ->assertSee('08:00–14:00');
    }

    public function test_nested_api_errors_are_shown(): void
    {
        Http::fake([self::API.'/api/clinic/hours' => Http::response(['days' => [[], ['closes' => ['Closing time must be after opening time.']]]], 400)]);
        $this->signedIn()->from('/settings/hours')->post('/settings/hours', ['days' => [2 => ['open' => '1', 'opens' => '08:00', 'closes' => '09:00']]])
            ->assertSessionHasErrors(['days' => 'days: Closing time must be after opening time.']);
    }
}
