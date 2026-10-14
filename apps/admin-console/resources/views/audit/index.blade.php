@extends('layouts.app')
@section('title', 'Audit log')
@section('content')
<header class="page-header">
    <div>
        <h1>Audit log</h1>
        <p class="subtitle">Every sign-in, record access and patient-flow change across MediFlow. Read-only. Viewing this page is itself logged.</p>
    </div>
</header>

<form method="GET" action="{{ route('audit') }}" class="filters panel">
    <div class="field"><label for="action">Action starts with</label><input id="action" name="action" value="{{ $filters['action'] ?? '' }}" placeholder="patient. or auth.login"></div>
    <div class="field"><label for="actor">Staff username</label><input id="actor" name="actor" value="{{ $filters['actor'] ?? '' }}"></div>
    <div class="field"><label for="entity_type">Record type</label>
        <select id="entity_type" name="entity_type">
            <option value="">Any</option>
            @foreach (['patient', 'visit', 'user', 'department', 'ai', 'audit'] as $type)
                <option value="{{ $type }}" @selected(($filters['entity_type'] ?? '') === $type)>{{ $type }}</option>
            @endforeach
        </select>
    </div>
    <div class="field"><label for="entity_id">Record ID</label><input id="entity_id" name="entity_id" value="{{ $filters['entity_id'] ?? '' }}"></div>
    <div class="field"><label for="since">From</label><input type="date" id="since" name="since" value="{{ $filters['since'] ?? '' }}"></div>
    <div class="field"><label for="until">To</label><input type="date" id="until" name="until" value="{{ $filters['until'] ?? '' }}"></div>
    <button type="submit" class="btn">Filter</button>
    <a href="{{ route('audit') }}" class="btn btn-secondary">Clear</a>
</form>

@if ($errors->any())<div class="error-box" role="alert">{{ $errors->first() }}</div>@endif
@if ($error)<div class="error-box" role="alert">{{ $error }}</div>@endif

<section class="panel">
    <h2>{{ number_format($count) }} {{ \Illuminate\Support\Str::plural('entry', $count) }}</h2>
    @include('audit._table', ['entries' => $entries])
    @if ($pages > 1)
        <nav class="pager" aria-label="Pages">
            @if ($page > 1)<a class="btn btn-secondary" href="{{ route('audit', $filters + ['page' => $page - 1]) }}">← Newer</a>@endif
            <span class="muted">Page {{ $page }} of {{ $pages }}</span>
            @if ($page < $pages)<a class="btn btn-secondary" href="{{ route('audit', $filters + ['page' => $page + 1]) }}">Older →</a>@endif
        </nav>
    @endif
</section>
@endsection
