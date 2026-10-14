@extends('layouts.app')
@section('title', 'Flow reports')
@section('content')
<header class="page-header">
    <div>
        <h1>Flow reports</h1>
        <p class="subtitle">Check-ins, waits and consultation times. Up to 92 days, in the hospital's time zone. No patient names are included.</p>
    </div>
</header>

<form method="GET" action="{{ route('reports') }}" class="filters panel">
    <div class="field"><label for="from">From</label><input type="date" id="from" name="from" value="{{ $from ?? $report['from'] ?? '' }}"></div>
    <div class="field"><label for="to">To</label><input type="date" id="to" name="to" value="{{ $to ?? $report['to'] ?? '' }}"></div>
    <button type="submit" class="btn">Show report</button>
    @if ($report)
        <a class="btn btn-secondary" href="{{ route('reports.csv', array_filter(['from' => $report['from'], 'to' => $report['to']])) }}">Download CSV</a>
    @endif
</form>

@if ($errors->any())<div class="error-box" role="alert">{{ $errors->first() }}</div>@endif
@if ($error)<div class="error-box" role="alert">{{ $error }}</div>@endif

@if ($report)
    @php($t = $report['totals'])
    <div class="stats">
        <div class="stat"><div class="stat-label">Check-ins</div><div class="stat-value">{{ $t['checkIns'] }}</div></div>
        <div class="stat"><div class="stat-label">Completed</div><div class="stat-value">{{ $t['completed'] }}</div></div>
        <div class="stat"><div class="stat-label">Cancelled</div><div class="stat-value">{{ $t['cancelled'] }}</div></div>
        <div class="stat"><div class="stat-label">Average wait</div><div class="stat-value">{{ isset($t['averageWaitMinutes']) ? $t['averageWaitMinutes'].' min' : '—' }}</div><div class="stat-hint">Check-in to called</div></div>
        <div class="stat"><div class="stat-label">Average consultation</div><div class="stat-value">{{ isset($t['averageConsultationMinutes']) ? $t['averageConsultationMinutes'].' min' : '—' }}</div></div>
    </div>

    <section class="panel">
        <h2>By day · {{ $report['from'] }} to {{ $report['to'] }}</h2>
        @include('reports._bars', ['days' => $report['days']])
    </section>

    <div class="split">
        <section class="panel">
            <h2>By department</h2>
            @include('reports._stats_table', ['rows' => $report['byDepartment'], 'key' => 'department', 'label' => 'Department'])
        </section>
        <section class="panel">
            <h2>By triage level</h2>
            @include('reports._stats_table', ['rows' => $report['byEsi'], 'key' => 'esi', 'label' => 'ESI'])
        </section>
    </div>
@endif
@endsection
