<?php

namespace App\Http\Controllers;

use App\Services\MediflowClient;
use Illuminate\View\View;

class DashboardController extends Controller
{
    public function __invoke(MediflowClient $mediflow): View
    {
        return view('dashboard', [
            'today' => $mediflow->flowToday(),
            'week' => $mediflow->flowReport(null, null),
            'recent' => $mediflow->auditLogs([], 1, 8)['results'] ?? [],
        ]);
    }
}
