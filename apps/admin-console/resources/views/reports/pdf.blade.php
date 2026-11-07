<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>MediFlow flow report {{ $report['from'] }} to {{ $report['to'] }}</title>
    <style>
        @page { margin: 28px 32px; }
        body { font-family: DejaVu Sans, sans-serif; font-size: 10px; color: #16262b; }
        h1 { font-size: 17px; margin: 0 0 2px; }
        h2 { font-size: 12px; margin: 0 0 6px; }
        .subtitle, .muted { color: #4c6066; }
        .small { font-size: 9px; }
        .panel { margin: 0 0 14px; page-break-inside: avoid; }
        .split .panel { width: 49%; display: inline-block; vertical-align: top; }
        .split .panel + .panel { margin-left: 1.5%; }
        table { width: 100%; border-collapse: collapse; }
        th { text-align: left; font-size: 9px; color: #4c6066; border-bottom: 1px solid #c8d3d1; padding: 3px 4px; }
        td { border-bottom: 1px solid #e3e9e8; padding: 3px 4px; }
        .num { text-align: right; }
        .hot { font-weight: bold; color: #a1332b; }
        .row-muted td { color: #8a9a9e; }
        tr.total td { font-weight: bold; }
        .stats td { border: none; padding: 0 12px 0 0; }
        .stat-value { font-size: 15px; font-weight: bold; }
        .foot { position: fixed; bottom: -12px; left: 0; right: 0; font-size: 8px; color: #8a9a9e; }
    </style>
</head>
<body>
    <h1>Patient flow report</h1>
    <p class="subtitle">{{ $report['from'] }} to {{ $report['to'] }} · {{ $report['timeZone'] }} · generated {{ $generatedAt }} by {{ $generatedBy }}</p>

    @php($t = $report['totals'])
    <table class="stats panel"><tr>
        @foreach ([['Check-ins', $t['checkIns']], ['Completed', $t['completed']], ['Cancelled', $t['cancelled']],
                   ['Average wait', isset($t['averageWaitMinutes']) ? $t['averageWaitMinutes'].' min' : '—'],
                   ['Average consultation', isset($t['averageConsultationMinutes']) ? $t['averageConsultationMinutes'].' min' : '—'],
                   ['Within ESI target', isset($t['seenWithinTargetPercent']) ? $t['seenWithinTargetPercent'].'%' : '—']] as [$label, $value])
            <td><div class="muted small">{{ $label }}</div><div class="stat-value">{{ $value }}</div></td>
        @endforeach
    </tr></table>

    <section class="panel">
        <h2>By department</h2>
        @include('reports._stats_table', ['rows' => $report['byDepartment'], 'key' => 'department', 'label' => 'Department'])
    </section>

    @include('reports._details', ['report' => $report, 'pdf' => true])

    <section class="panel">
        <h2>By day</h2>
        @include('reports._stats_table', ['rows' => $report['days'], 'key' => 'date', 'label' => 'Date'])
    </section>

    <div class="foot">MediFlow · contains no patient-identifiable data</div>
</body>
</html>
