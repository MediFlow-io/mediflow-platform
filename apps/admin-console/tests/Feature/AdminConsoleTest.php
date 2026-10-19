<?php

namespace Tests\Feature;

use App\Services\MediflowClient;
use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

class AdminConsoleTest extends TestCase
{
    private const GATEWAY = 'http://gateway.test';
    private const API = 'http://api.test';
    private const FLOW = 'http://flow.test';

    protected function setUp(): void
    {
        parent::setUp();
        config(['mediflow.gateway_url' => self::GATEWAY, 'mediflow.api_url' => self::API, 'mediflow.flow_url' => self::FLOW]);
    }

    private function signedIn(): self
    {
        return $this->withSession([MediflowClient::SESSION_KEY => [
            'access' => 'ACCESS-1', 'refresh' => 'REFRESH-1', 'user' => ['id' => 1, 'username' => 'admin', 'name' => 'Ada Admin'],
        ]]);
    }

    private function report(): array
    {
        $day = ['checkIns' => 3, 'completed' => 2, 'cancelled' => 1, 'averageWaitMinutes' => 12, 'averageConsultationMinutes' => 9];

        return [
            'from' => '2026-10-07', 'to' => '2026-10-13', 'timeZone' => 'Africa/Lagos', 'totals' => $day,
            'days' => [['date' => '2026-10-07'] + $day, ['date' => '2026-10-08', 'checkIns' => 0, 'completed' => 0, 'cancelled' => 0, 'averageWaitMinutes' => null, 'averageConsultationMinutes' => null]],
            'byDepartment' => [['department' => 'Outpatient'] + $day], 'byEsi' => [['esi' => 2] + $day],
        ];
    }

    private function audit(): array
    {
        return ['count' => 1, 'next' => null, 'previous' => null, 'results' => [[
            'id' => 9, 'created_at' => '2026-10-13T10:00:00+01:00', 'actor' => 'nurse', 'actor_role' => 'nurse',
            'action' => 'patient.viewed', 'entity_type' => 'patient', 'entity_id' => '7', 'details' => [],
        ]]];
    }

    // ---------------------------------------------------------------- access

    public function test_guests_are_sent_to_sign_in(): void
    {
        foreach (['/', '/audit', '/reports', '/reports/flow.csv', '/departments'] as $path) {
            $this->get($path)->assertRedirect('/login');
        }
        $this->get('/login')->assertOk()->assertSee('Admin console');
    }

    public function test_admin_signs_in_and_tokens_stay_on_the_server(): void
    {
        Http::fake([self::GATEWAY.'/api/auth/login' => Http::response(['id' => 1, 'username' => 'admin', 'name' => 'Ada Admin', 'role' => 'admin', 'access' => 'A', 'refresh' => 'R'])]);

        $response = $this->post('/login', ['username' => 'admin', 'password' => 'secret-pass']);

        $response->assertRedirect('/');
        $this->assertSame('A', session(MediflowClient::SESSION_KEY.'.access'));
        $this->assertStringNotContainsString('A', implode(' ', $response->headers->getCookies() ? array_map(fn ($c) => $c->getName(), $response->headers->getCookies()) : []));
        Http::assertSent(fn (Request $r) => $r->url() === self::GATEWAY.'/api/auth/login' && $r['unique_id'] === 'admin');
    }

    public function test_non_admins_are_refused_and_their_token_revoked(): void
    {
        Http::fake([
            self::GATEWAY.'/api/auth/login' => Http::response(['id' => 2, 'username' => 'nurse', 'role' => 'nurse', 'access' => 'A', 'refresh' => 'R']),
            self::GATEWAY.'/api/auth/logout' => Http::response(['message' => 'ok']),
        ]);

        $this->post('/login', ['username' => 'nurse', 'password' => 'secret-pass'])
            ->assertSessionHasErrors(['username' => 'The admin console is for administrators only.']);

        $this->assertNull(session(MediflowClient::SESSION_KEY));
        Http::assertSent(fn (Request $r) => $r->url() === self::GATEWAY.'/api/auth/logout' && $r['refresh'] === 'R');
    }

    public function test_two_step_sign_in_asks_for_a_code(): void
    {
        Http::fake([
            self::GATEWAY.'/api/auth/login' => Http::response(['mfa_required' => true, 'mfa_token' => 'CHALLENGE']),
            self::GATEWAY.'/api/auth/mfa/verify' => Http::sequence()
                ->push(['detail' => "That code isn't right."], 401)
                ->push(['id' => 1, 'username' => 'admin', 'name' => 'Ada Admin', 'role' => 'admin', 'access' => 'A', 'refresh' => 'R']),
        ]);
        $this->get('/login/code')->assertRedirect('/login');

        $this->post('/login', ['username' => 'admin', 'password' => 'secret-pass'])->assertRedirect('/login/code');
        $this->assertNull(session(MediflowClient::SESSION_KEY), 'no tokens before the code');
        $this->get('/login/code')->assertOk()->assertSee('Authentication code');
        $this->post('/login/code', ['code' => '12ab'])->assertSessionHasErrors('code');
        $this->post('/login/code', ['code' => '123456'])->assertRedirect('/login/code')
            ->assertSessionHasErrors(['code' => "That code isn't right."]);
        $this->post('/login/code', ['code' => '654321'])->assertRedirect('/');
        $this->assertSame('A', session(MediflowClient::SESSION_KEY.'.access'));
        $this->assertNull(session(MediflowClient::MFA_KEY));
        Http::assertSent(fn (Request $r) => str_ends_with($r->url(), '/api/auth/mfa/verify') && $r['mfa_token'] === 'CHALLENGE' && $r['code'] === '654321');
    }

    public function test_wrong_password_shows_the_api_message(): void
    {
        Http::fake([self::GATEWAY.'/api/auth/login' => Http::response(['detail' => 'Invalid credentials.'], 401)]);
        $this->post('/login', ['username' => 'admin', 'password' => 'nope'])->assertSessionHasErrors(['username' => 'Invalid credentials.']);
    }

    public function test_expired_token_is_refreshed_once_and_rotated(): void
    {
        Http::fake([
            self::GATEWAY.'/api/auth/token/refresh' => Http::response(['access' => 'ACCESS-2', 'refresh' => 'REFRESH-2']),
            self::API.'/api/departments' => Http::sequence()->push(['detail' => 'expired'], 401)->push([]),
        ]);

        $this->signedIn()->get('/departments')->assertOk();

        $this->assertSame('ACCESS-2', session(MediflowClient::SESSION_KEY.'.access'));
        $this->assertSame('REFRESH-2', session(MediflowClient::SESSION_KEY.'.refresh'));
        Http::assertSent(fn (Request $r) => str_ends_with($r->url(), '/api/departments') && $r->hasHeader('Authorization', 'Bearer ACCESS-2'));
    }

    public function test_failed_refresh_ends_the_session(): void
    {
        Http::fake([
            self::GATEWAY.'/*' => Http::response(['detail' => 'revoked'], 401),
            self::API.'/*' => Http::response(['detail' => 'expired'], 401),
        ]);
        $this->signedIn()->get('/departments')->assertRedirect('/login')->assertSessionHasErrors('session');
    }

    public function test_losing_admin_rights_ends_the_session(): void
    {
        Http::fake([
            self::API.'/*' => Http::response(['detail' => 'You do not have permission to perform this action.'], 403),
            self::GATEWAY.'/*' => Http::response([]),
        ]);
        $this->signedIn()->get('/departments')->assertRedirect('/login')
            ->assertSessionHasErrors(['session' => 'Your account no longer has administrator access.']);
    }

    public function test_unreachable_service_shows_a_friendly_error(): void
    {
        Http::fake(fn () => throw new \Illuminate\Http\Client\ConnectionException('down'));
        $this->signedIn()->get('/departments')->assertStatus(502)->assertSee('could not be reached');
    }

    // ---------------------------------------------------------------- pages

    public function test_overview(): void
    {
        Http::fake([
            self::FLOW.'/api/dashboard' => Http::response(['currentlyWaiting' => 4, 'emergencyCases' => 1, 'inConsultation' => 2, 'patientsToday' => 9, 'completedToday' => 5, 'averageWaitMinutes' => 14]),
            self::FLOW.'/api/reports/flow*' => Http::response($this->report()),
            self::API.'/api/audit-logs*' => Http::response($this->audit()),
        ]);
        $this->signedIn()->get('/')->assertOk()
            ->assertSee('Waiting now')->assertSee('1 emergency (ESI 1–2)')->assertSee('14 min')
            ->assertSee('patient.viewed')->assertSee('Ada Admin');
    }

    public function test_audit_log_passes_filters_and_paginates(): void
    {
        Http::fake([self::API.'/api/audit-logs*' => Http::response(['count' => 120] + $this->audit())]);

        $this->signedIn()->get('/audit?action=patient.&actor=nurse&page=2')->assertOk()
            ->assertSee('120 entries')->assertSee('Page 2 of 3')->assertSee('← Newer')->assertSee('Older →');

        Http::assertSent(fn (Request $r) => str_contains($r->url(), '/api/audit-logs')
            && $r['action'] === 'patient.' && $r['actor'] === 'nurse' && (int) $r['page'] === 2 && (int) $r['page_size'] === 50);
    }

    public function test_audit_log_validates_dates(): void
    {
        Http::fake();
        $this->signedIn()->get('/audit?since=13-10-2026')->assertRedirect();
        Http::assertNothingSent();
    }

    public function test_flow_report_and_csv_export(): void
    {
        Http::fake([self::FLOW.'/api/reports/flow*' => Http::response($this->report())]);

        $this->signedIn()->get('/reports?from=2026-10-07&to=2026-10-13')->assertOk()
            ->assertSee('Outpatient')->assertSee('ESI 2')->assertSee('Download CSV');
        Http::assertSent(fn (Request $r) => $r['from'] === '2026-10-07' && $r['to'] === '2026-10-13');

        $csv = $this->signedIn()->get('/reports/flow.csv?from=2026-10-07&to=2026-10-13');
        $csv->assertOk()->assertHeader('Content-Type', 'text/csv; charset=UTF-8')
            ->assertDownload('mediflow-flow-2026-10-07-to-2026-10-13.csv');
        $lines = array_values(array_filter(explode("\n", $csv->streamedContent())));
        $this->assertSame('date,check_ins,completed,cancelled,average_wait_minutes,average_consultation_minutes', $lines[0]);
        $this->assertSame('2026-10-07,3,2,1,12,9', $lines[1]);
        $this->assertSame('2026-10-08,0,0,0,,', $lines[2]);
    }

    public function test_report_range_errors_from_go_are_shown(): void
    {
        Http::fake([self::FLOW.'/api/reports/flow*' => Http::response(['to' => ['A report can cover at most 92 days.']], 400)]);
        $this->signedIn()->get('/reports?from=2026-01-01&to=2026-10-13')->assertOk()->assertSee('at most 92 days');
    }

    public function test_departments_create_and_close(): void
    {
        Http::fake([
            self::API.'/api/departments' => Http::sequence()
                ->push(['id' => 5, 'name' => 'Dental Clinic', 'code' => 'dental', 'active' => true], 201)
                ->push(['code' => ['department with this code already exists.']], 400),
            self::API.'/api/departments/5' => Http::response(['id' => 5, 'name' => 'Dental Clinic', 'code' => 'dental', 'active' => false]),
        ]);

        $this->signedIn()->post('/departments', ['name' => 'Dental Clinic', 'code' => 'dental'])
            ->assertRedirect('/departments')->assertSessionHas('status', 'Department “Dental Clinic” created.');
        $this->signedIn()->post('/departments', ['name' => 'Dental Clinic', 'code' => 'dental'])
            ->assertSessionHasErrors(['code' => 'department with this code already exists.']);
        $this->signedIn()->patch('/departments/5', ['active' => 0])->assertSessionHas('status', '“Dental Clinic” closed: new check-ins are blocked.');

        Http::assertSent(fn (Request $r) => $r->method() === 'PATCH' && $r['active'] === false);
    }

    public function test_department_code_is_validated_before_calling_the_api(): void
    {
        Http::fake();
        $this->signedIn()->post('/departments', ['name' => 'X', 'code' => 'Has Spaces'])->assertSessionHasErrors('code');
        Http::assertNothingSent();
    }

    public function test_sign_out_revokes_the_refresh_token(): void
    {
        Http::fake([self::GATEWAY.'/api/auth/logout' => Http::response(['message' => 'ok'])]);
        $this->signedIn()->post('/logout')->assertRedirect('/login');
        Http::assertSent(fn (Request $r) => str_ends_with($r->url(), '/api/auth/logout') && $r['refresh'] === 'REFRESH-1');
        $this->assertNull(session(MediflowClient::SESSION_KEY));
    }

    public function test_security_headers_and_health(): void
    {
        $this->get('/login')->assertHeader('X-Frame-Options', 'DENY')
            ->assertHeader('Content-Security-Policy')->assertHeader('X-Content-Type-Options', 'nosniff');
        $this->get('/up')->assertOk();
    }
}
