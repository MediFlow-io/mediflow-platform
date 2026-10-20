@extends('layouts.app')
@section('title', 'Opening hours')
@section('content')
<header class="page-header">
    <div>
        <h1>Opening hours</h1>
        <p class="subtitle">When appointments can be booked. Departments use the clinic default unless they have their own hours.</p>
    </div>
    <form method="GET" action="{{ route('settings.hours') }}" class="inline">
        <label for="department" class="small">Hours for</label>
        <select id="department" name="department">
            <option value="">Clinic default</option>
            @foreach ($departments as $department)
                <option value="{{ $department['id'] }}" @selected($selected === $department['id'])>{{ $department['name'] }}</option>
            @endforeach
        </select>
        <button type="submit" class="btn btn-small btn-secondary">Show</button>
    </form>
</header>

@if ($errors->any())<div class="error-box" role="alert">{{ implode(' ', $errors->all()) }}</div>@endif
@if ($selected === null && ! $hasDefault)
    <div class="info-box">No default hours are saved yet, so bookings use the fallback hours the patient-flow service was started with (CLINIC_HOURS / CLINIC_DAYS).</div>
@elseif ($usesDefault)
    <div class="info-box">This department uses the clinic default hours. Tick days below to give it its own hours.</div>
@endif

<section class="panel narrow-wide">
    <form method="POST" action="{{ route('settings.hours.save') }}">
        @csrf
        <input type="hidden" name="department" value="{{ $selected }}">
        <table class="table">
            <thead><tr><th>Day</th><th>Open</th><th>From</th><th>To</th></tr></thead>
            <tbody>
            @foreach ($weekdays as $weekday => $name)
                @php($day = $byDay[$weekday] ?? null)
                <tr>
                    <td><label for="open{{ $weekday }}">{{ $name }}</label></td>
                    <td><input id="open{{ $weekday }}" type="checkbox" name="days[{{ $weekday }}][open]" value="1"
                               @checked(old("days.$weekday.open", $day !== null))></td>
                    <td><input type="time" aria-label="{{ $name }} opens" name="days[{{ $weekday }}][opens]"
                               value="{{ old("days.$weekday.opens", $day ? substr($day['opens'], 0, 5) : '08:00') }}"></td>
                    <td><input type="time" aria-label="{{ $name }} closes" name="days[{{ $weekday }}][closes]"
                               value="{{ old("days.$weekday.closes", $day ? substr($day['closes'], 0, 5) : '16:00') }}"></td>
                </tr>
            @endforeach
            </tbody>
        </table>
        <button type="submit" class="btn">Save hours</button>
        @if ($selected !== null && ! $usesDefault)
            <span class="muted small">Untick every day and save to go back to the clinic default.</span>
        @endif
    </form>
</section>
@endsection
