{{-- Breakdowns shared by the reports page and its PDF. $report comes from GET /api/reports/flow. $pdf hides interactive bits. --}}
@php
    $min = fn ($v) => isset($v) ? $v.' min' : '—';
    $pct = fn ($v) => isset($v) ? $v.'%' : '—';
    $hours = array_values(array_filter($report['byHour'] ?? [], fn ($h) => $h['checkIns'] > 0));
    $maxHour = max([1, ...array_map(fn ($h) => $h['checkIns'], $hours)]);
    // Where time goes: the slowest stage per department is the likely bottleneck.
    $stages = [];
    foreach ($report['byDepartment'] ?? [] as $d) {
        $parts = ['Waiting to be called' => $d['averageWaitMinutes'] ?? null, 'Called to seen' => $d['averageCallToStartMinutes'] ?? null,
            'Consultation' => $d['averageConsultationMinutes'] ?? null];
        $known = array_filter($parts, fn ($v) => $v !== null);
        $stages[] = $d + ['slowest' => $known && max($known) > 0 ? array_search(max($known), $known, true) : null];
    }
@endphp

<section class="panel">
    <h2>Seen within ESI target</h2>
    <p class="muted small">Share of patients called or seen within their triage level’s target
        ({{ implode(', ', array_map(fn ($esi, $target) => "ESI $esi: $target min", array_keys($report['targetMinutes'] ?? []), $report['targetMinutes'] ?? [])) }}).</p>
    <table class="table">
        <thead><tr><th>Triage level</th><th class="num">Patients</th><th class="num">Avg wait</th><th class="num">Within target</th></tr></thead>
        <tbody>
        @foreach ($report['byEsi'] ?? [] as $row)
            <tr>
                <td>ESI {{ $row['esi'] }}</td>
                <td class="num">{{ $row['checkIns'] }}</td>
                <td class="num">{{ $min($row['averageWaitMinutes'] ?? null) }}</td>
                <td class="num">{{ $pct($row['seenWithinTargetPercent'] ?? null) }}</td>
            </tr>
        @endforeach
        <tr class="total"><td>All</td><td class="num">{{ $report['totals']['checkIns'] }}</td>
            <td class="num">{{ $min($report['totals']['averageWaitMinutes'] ?? null) }}</td>
            <td class="num">{{ $pct($report['totals']['seenWithinTargetPercent'] ?? null) }}</td></tr>
        </tbody>
    </table>
</section>

<section class="panel">
    <h2>Where the time goes</h2>
    <p class="muted small">Average minutes at each stage. The slowest stage in each department is highlighted: that is where to look first.</p>
    @if ($stages === [])
        <p class="muted empty">No visits in this period.</p>
    @else
        <table class="table">
            <thead><tr><th>Department</th><th class="num">Waiting to be called</th><th class="num">Called to seen</th><th class="num">Consultation</th></tr></thead>
            <tbody>
            @foreach ($stages as $d)
                <tr>
                    <td>{{ $d['department'] }}</td>
                    <td class="num {{ $d['slowest'] === 'Waiting to be called' ? 'hot' : '' }}">{{ $min($d['averageWaitMinutes'] ?? null) }}</td>
                    <td class="num {{ $d['slowest'] === 'Called to seen' ? 'hot' : '' }}">{{ $min($d['averageCallToStartMinutes'] ?? null) }}</td>
                    <td class="num {{ $d['slowest'] === 'Consultation' ? 'hot' : '' }}">{{ $min($d['averageConsultationMinutes'] ?? null) }}</td>
                </tr>
            @endforeach
            </tbody>
        </table>
    @endif
</section>

<div class="split">
    <section class="panel">
        <h2>Busiest hours</h2>
        @if ($hours === [])
            <p class="muted empty">No check-ins in this period.</p>
        @else
            <table class="table bars" aria-label="Check-ins by hour">
                <thead><tr><th>Hour</th>@unless ($pdf ?? false)<th>Check-ins</th>@endunless<th class="num">Count</th><th class="num">Avg wait</th></tr></thead>
                <tbody>
                @foreach ($hours as $h)
                    <tr>
                        <td class="nowrap">{{ sprintf('%02d:00', $h['hour']) }}</td>
                        @unless ($pdf ?? false)<td class="bar-cell"><meter class="bar" min="0" max="{{ $maxHour }}" value="{{ $h['checkIns'] }}"></meter></td>@endunless
                        <td class="num">{{ $h['checkIns'] }}</td>
                        <td class="num">{{ $min($h['averageWaitMinutes'] ?? null) }}</td>
                    </tr>
                @endforeach
                </tbody>
            </table>
        @endif
    </section>
    <section class="panel">
        <h2>By day of the week</h2>
        <table class="table">
            <thead><tr><th>Day</th><th class="num">Check-ins</th><th class="num">Avg wait</th><th class="num">Within target</th></tr></thead>
            <tbody>
            @foreach ($report['byWeekday'] ?? [] as $d)
                <tr class="{{ $d['checkIns'] ? '' : 'row-muted' }}">
                    <td>{{ $d['day'] }}</td>
                    <td class="num">{{ $d['checkIns'] }}</td>
                    <td class="num">{{ $min($d['averageWaitMinutes'] ?? null) }}</td>
                    <td class="num">{{ $pct($d['seenWithinTargetPercent'] ?? null) }}</td>
                </tr>
            @endforeach
            </tbody>
        </table>
    </section>
</div>

<section class="panel">
    <h2>Clinician workload</h2>
    @if (($report['byClinician'] ?? []) === [])
        <p class="muted empty">No visits were assigned to a clinician in this period.</p>
    @else
        <table class="table">
            <thead><tr><th>Clinician</th><th class="num">Patients</th><th class="num">Completed</th><th class="num">Avg consultation</th></tr></thead>
            <tbody>
            @foreach ($report['byClinician'] as $c)
                <tr>
                    <td>{{ $c['clinician'] }}</td>
                    <td class="num">{{ $c['checkIns'] }}</td>
                    <td class="num">{{ $c['completed'] }}</td>
                    <td class="num">{{ $min($c['averageConsultationMinutes'] ?? null) }}</td>
                </tr>
            @endforeach
            </tbody>
        </table>
    @endif
</section>
