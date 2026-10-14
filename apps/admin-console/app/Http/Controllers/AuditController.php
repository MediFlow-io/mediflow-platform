<?php

namespace App\Http\Controllers;

use App\Exceptions\MediflowException;
use App\Services\MediflowClient;
use Illuminate\Http\Request;
use Illuminate\View\View;

/** Read-only view of the shared audit log: who did what, when. Viewing it is itself audited. */
class AuditController extends Controller
{
    private const PAGE_SIZE = 50;

    public function index(Request $request, MediflowClient $mediflow): View
    {
        $filters = $request->validate([
            'action' => ['nullable', 'string', 'max:100'],
            'actor' => ['nullable', 'string', 'max:150'],
            'entity_type' => ['nullable', 'string', 'max:64'],
            'entity_id' => ['nullable', 'string', 'max:64'],
            'since' => ['nullable', 'date_format:Y-m-d'],
            'until' => ['nullable', 'date_format:Y-m-d', 'after_or_equal:since'],
        ]);
        $page = max(1, (int) $request->query('page', 1));
        $error = null;
        try {
            $data = $mediflow->auditLogs($filters, $page, self::PAGE_SIZE);
        } catch (MediflowException $e) {
            if ($e->status !== 400 && $e->status !== 404) {
                throw $e;
            }
            $data = ['count' => 0, 'results' => []];
            $error = $e->status === 404 ? 'That page does not exist.' : $e->getMessage();
        }

        return view('audit.index', [
            'filters' => $filters,
            'entries' => $data['results'] ?? [],
            'count' => $data['count'] ?? 0,
            'page' => $page,
            'pages' => max(1, (int) ceil(($data['count'] ?? 0) / self::PAGE_SIZE)),
            'error' => $error,
        ]);
    }
}
