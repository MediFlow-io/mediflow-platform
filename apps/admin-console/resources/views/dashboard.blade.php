@extends('layouts.app')
@section('title', 'Overview')
@section('content')
<header class="page-header">
    <div>
        <h1>Overview</h1>
        <p class="subtitle">Today's patient flow and the last 7 days ({{ $week['from'] }} to {{ $week['to'] }}).</p>
    </div>
</header>

<div class="stats">
    @foreach ([
        ['Waiting now', $today['currentlyWaiting'], $today['emergencyCases'] ? "{$today['emergencyCases']} emergency (ESI 1–2)" : null],
        ['In consultation', $today['inConsultation'], null],
        ['Patients today', $today['patientsToday'], null],
        ['Completed today', $today['completedToday'], null],
        ['Average wait today', isset($today['averageWaitMinutes']) ? $today['averageWaitMinutes'].' min' : '—', 'Check-in to called'],
        ['Check-ins, 7 days', $week['totals']['checkIns'], isset($week['totals']['averageWaitMinutes']) ? "avg wait {$week['totals']['averageWaitMinutes']} min" : null],
    ] as [$label, $value, $hint])
        <div class="stat">
            <div class="stat-label">{{ $label }}</div>
            <div class="stat-value">{{ $value }}</div>
            @if ($hint)<div class="stat-hint">{{ $hint }}</div>@endif
        </div>
    @endforeach
</div>

<div class="split">
    <section class="panel">
        <h2>Check-ins per day</h2>
        @include('reports._bars', ['days' => $week['days']])
        <p class="small"><a href="{{ route('reports') }}">Open flow reports →</a></p>
    </section>
    <section class="panel">
        <h2>Recent activity</h2>
        @include('audit._table', ['entries' => $recent, 'compact' => true])
        <p class="small"><a href="{{ route('audit') }}">Open the audit log →</a></p>
    </section>
</div>
@endsection
