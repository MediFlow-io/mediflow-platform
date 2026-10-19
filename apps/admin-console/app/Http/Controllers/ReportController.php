<?php

namespace App\Http\Controllers;

use App\Exceptions\MediflowException;
use App\Services\MediflowClient;
use Barryvdh\DomPDF\Facade\Pdf;
use Illuminate\Http\Response;
use Illuminate\Http\Request;
use Illuminate\View\View;
use Symfony\Component\HttpFoundation\StreamedResponse;

/** Patient-flow reports over a date range, computed by the Go patient-flow service. */
class ReportController extends Controller
{
    public function index(Request $request, MediflowClient $mediflow): View
    {
        [$from, $to] = $this->range($request);
        try {
            $report = $mediflow->flowReport($from, $to);
            $error = null;
        } catch (MediflowException $e) {
            if ($e->status !== 400) {
                throw $e;
            }
            [$report, $error] = [null, $e->getMessage()];
        }

        return view('reports.index', ['report' => $report, 'error' => $error, 'from' => $from, 'to' => $to]);
    }

    /** CSV of the daily rows, for spreadsheets. Contains no patient-identifiable data. */
    public function csv(Request $request, MediflowClient $mediflow): StreamedResponse
    {
        [$from, $to] = $this->range($request);
        $report = $mediflow->flowReport($from, $to);
        $filename = sprintf('mediflow-flow-%s-to-%s.csv', $report['from'], $report['to']);

        return response()->streamDownload(function () use ($report) {
            $out = fopen('php://output', 'w');
            fputcsv($out, ['date', 'check_ins', 'completed', 'cancelled', 'average_wait_minutes', 'average_consultation_minutes']);
            foreach ($report['days'] as $day) {
                fputcsv($out, [$day['date'], $day['checkIns'], $day['completed'], $day['cancelled'],
                    $day['averageWaitMinutes'] ?? '', $day['averageConsultationMinutes'] ?? '']);
            }
            fclose($out);
        }, $filename, ['Content-Type' => 'text/csv; charset=UTF-8']);
    }

    /** The same report as a PDF, for printing or sharing. Contains no patient-identifiable data. */
    public function pdf(Request $request, MediflowClient $mediflow): Response
    {
        [$from, $to] = $this->range($request);
        $report = $mediflow->flowReport($from, $to);
        $html = view('reports.pdf', [
            'report' => $report,
            'generatedAt' => now($report['timeZone'] ?? 'UTC')->format('D j M Y, H:i'),
            'generatedBy' => $mediflow->user()['name'] ?? 'an administrator',
        ])->render();
        $pdf = Pdf::loadHTML($html)->setPaper('a4')->setOption(['isRemoteEnabled' => false]);

        return $pdf->download(sprintf('mediflow-flow-%s-to-%s.pdf', $report['from'], $report['to']));
    }

    /** @return array{0: ?string, 1: ?string} */
    private function range(Request $request): array
    {
        $valid = $request->validate([
            'from' => ['nullable', 'date_format:Y-m-d'],
            'to' => ['nullable', 'date_format:Y-m-d', 'after_or_equal:from'],
        ]);

        return [$valid['from'] ?? null, $valid['to'] ?? null];
    }
}
