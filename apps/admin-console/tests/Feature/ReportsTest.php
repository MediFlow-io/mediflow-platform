<?php

namespace Tests\Feature;

use App\Services\MediflowClient;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

class ReportsTest extends TestCase
{
    private const FLOW = 'http://flow.test';

    protected function setUp(): void
    {
        parent::setUp();
        config(['mediflow.gateway_url' => 'http://gateway.test', 'mediflow.api_url' => 'http://api.test', 'mediflow.flow_url' => self::FLOW]);
    }

    private function signedIn(): self
    {
        return $this->withSession([MediflowClient::SESSION_KEY => [
            'access' => 'ACCESS-1', 'refresh' => 'REFRESH-1', 'user' => ['id' => 1, 'username' => 'admin', 'name' => 'Ada Admin'],
        ]]);
    }

    private function stats(array $overrides = []): array
    {
        return $overrides + ['checkIns' => 4, 'completed' => 3, 'cancelled' => 1, 'averageWaitMinutes' => 25,
            'averageConsultationMinutes' => 12, 'averageCallToStartMinutes' => 4, 'seenWithinTargetPercent' => 75];
    }

    private function report(): array
    {
        $hours = [];
        for ($h = 0; $h < 24; $h++) {
            $hours[] = ['hour' => $h] + ($h === 9 ? $this->stats() : $this->stats(['checkIns' => 0, 'averageWaitMinutes' => null]));
        }
        $weekdays = [];
        foreach (['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'] as $i => $day) {
            $weekdays[] = ['weekday' => $i, 'day' => $day] + $this->stats(['checkIns' => $i === 1 ? 4 : 0]);
        }

        return [
            'from' => '2026-10-13', 'to' => '2026-10-19', 'timeZone' => 'Africa/Lagos', 'totals' => $this->stats(),
            'days' => [['date' => '2026-10-13'] + $this->stats()],
            'byDepartment' => [['department' => 'Outpatient'] + $this->stats(['averageWaitMinutes' => 40])],
            'byEsi' => [['esi' => 3] + $this->stats()],
            'byHour' => $hours, 'byWeekday' => $weekdays,
            'byClinician' => [['clinician' => 'Dr Demo'] + $this->stats(['completed' => 3])],
            'targetMinutes' => ['1' => 0, '2' => 10, '3' => 30, '4' => 60, '5' => 120],
        ];
    }

    public function test_report_page_shows_targets_bottlenecks_hours_and_workload(): void
    {
        Http::fake([self::FLOW.'/api/reports/flow*' => Http::response($this->report())]);
        $this->signedIn()->get('/reports')->assertOk()
            ->assertSee('Seen within ESI target')->assertSee('75%')
            ->assertSee('Where the time goes')->assertSee('<td class="num hot">40 min</td>', false)
            ->assertSee('09:00')->assertDontSee('03:00')
            ->assertSee('Dr Demo')
            ->assertSee('ESI 2: 10 min')
            ->assertSee('Download PDF');
    }

    public function test_pdf_download(): void
    {
        Http::fake([self::FLOW.'/api/reports/flow*' => Http::response($this->report())]);
        $response = $this->signedIn()->get('/reports/flow.pdf?from=2026-10-13&to=2026-10-19');
        $response->assertOk()->assertHeader('Content-Type', 'application/pdf')
            ->assertDownload('mediflow-flow-2026-10-13-to-2026-10-19.pdf');
        $this->assertStringStartsWith('%PDF', $response->getContent());
        Http::assertSent(fn ($r) => str_contains($r->url(), 'from=2026-10-13') && str_contains($r->url(), 'to=2026-10-19'));
    }

    public function test_pdf_needs_sign_in_and_a_valid_range(): void
    {
        $this->get('/reports/flow.pdf')->assertRedirect('/login');
        Http::fake();
        $this->signedIn()->get('/reports/flow.pdf?from=2026-10-19&to=2026-10-01')->assertSessionHasErrors('to');
        Http::assertNothingSent();
    }
}
