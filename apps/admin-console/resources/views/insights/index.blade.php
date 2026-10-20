@extends('layouts.app')
@section('title', 'AI insights')
@section('content')
<header class="page-header">
    <div>
        <h1>AI insights</h1>
        <p class="subtitle">Where patient flow is getting stuck and how long a new arrival would wait. Decision support: check the numbers before acting.</p>
    </div>
</header>

@if ($error)<div class="error-box" role="alert">{{ $error }}</div>@endif

@if ($insights)
    <section class="panel">
        <h2>What to look at · last {{ $insights['periodDays'] }} days</h2>
        @if ($insights['findings'] === [])
            <p class="muted empty">Nothing stands out. Flow looks healthy, or there are too few visits to judge.</p>
        @else
            <ul class="findings">
                @foreach ($insights['findings'] as $f)
                    <li class="finding finding-{{ $f['severity'] }}">
                        <span class="badge {{ $f['severity'] === 'high' ? 'badge-off' : ($f['severity'] === 'medium' ? 'badge-warn' : 'badge-ok') }}">{{ ucfirst($f['severity']) }}</span>
                        <strong>{{ $f['department'] }}</strong> · {{ $f['message'] }}
                    </li>
                @endforeach
            </ul>
        @endif
    </section>

    <section class="panel">
        <h2>Expected wait for a new arrival</h2>
        <table class="table">
            <thead><tr><th>Department</th><th class="num">Waiting now</th><th class="num">Expected</th><th class="num">Likely range</th><th>Confidence</th></tr></thead>
            <tbody>
            @foreach ($insights['departments'] as $d)
                @php($w = $d['expectedWaitForNewArrival'])
                <tr>
                    <td>{{ $d['name'] }}</td>
                    <td class="num">{{ $d['waitingNow'] }}</td>
                    <td class="num">{{ $w['expected_minutes'] }} min</td>
                    <td class="num">{{ $w['low_minutes'] }}–{{ $w['high_minutes'] }} min</td>
                    <td>{{ $w['confidence'] }} <span class="muted small">({{ $w['basis'] }})</span></td>
                </tr>
            @endforeach
            </tbody>
        </table>
        <p class="muted small">Assumes the same mix of patients; a more urgent arrival moves ahead. Model {{ $insights['modelVersion'] ?? '—' }}.</p>
    </section>
@endif
@endsection
