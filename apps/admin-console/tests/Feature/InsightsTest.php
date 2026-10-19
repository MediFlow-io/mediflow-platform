<?php

namespace Tests\Feature;

use App\Services\MediflowClient;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

class InsightsTest extends TestCase
{
    protected function setUp(): void
    {
        parent::setUp();
        config(['mediflow.gateway_url' => 'http://gateway.test', 'mediflow.api_url' => 'http://api.test', 'mediflow.flow_url' => 'http://flow.test']);
    }

    private function signedIn(): self
    {
        return $this->withSession([MediflowClient::SESSION_KEY => [
            'access' => 'A', 'refresh' => 'R', 'user' => ['id' => 1, 'username' => 'admin', 'name' => 'Ada Admin'],
        ]]);
    }

    public function test_insights_show_findings_and_expected_waits(): void
    {
        Http::fake(['http://api.test/api/ai/insights' => Http::response([
            'periodDays' => 14, 'generatedAt' => '2026-10-19T12:00:00Z', 'modelVersion' => 'flow-stats-2026.10',
            'findings' => [['severity' => 'high', 'department' => 'Outpatient', 'stage' => 'waiting', 'message' => 'Patients wait 70 min to be called.']],
            'departments' => [['name' => 'Outpatient', 'waitingNow' => 6, 'checkIns' => 80, 'expectedWaitForNewArrival' => [
                'expected_minutes' => 45, 'low_minutes' => 30, 'high_minutes' => 60, 'confidence' => 'high', 'basis' => '120 recent consultations (mean 15 min)',
            ]]],
        ])]);
        $this->signedIn()->get('/insights')->assertOk()
            ->assertSee('Patients wait 70 min to be called.')->assertSee('30–60 min')->assertSee('120 recent consultations');
        $this->get('/insights')->assertOk(); // session kept
    }

    public function test_ai_outage_is_explained(): void
    {
        Http::fake(['http://api.test/api/ai/insights' => Http::response(['detail' => 'The AI assistant is unavailable right now.'], 503)]);
        $this->signedIn()->get('/insights')->assertOk()->assertSee('The AI assistant is unavailable right now.');
    }

    public function test_guests_go_to_sign_in(): void
    {
        $this->get('/insights')->assertRedirect('/login');
    }
}
