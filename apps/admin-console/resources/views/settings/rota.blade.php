@extends('layouts.app')
@section('title', 'Staff rota')
@section('content')
<header class="page-header">
    <div>
        <h1>Staff rota</h1>
        <p class="subtitle">Who works where, by weekday. Wait estimates count the doctors on shift, and urgent-patient alerts go to the doctors and nurses on shift in that department.</p>
    </div>
</header>

@if ($errors->any())<div class="error-box" role="alert">{{ $errors->first() }}</div>@endif

<div class="split">
    <section class="panel">
        <h2>This week</h2>
        @foreach ($weekdays as $weekday => $name)
            <h3>{{ $name }}</h3>
            @if ($byDay[$weekday] === [])
                <p class="muted small">Nobody rostered.</p>
            @else
                <table class="table" aria-label="{{ $name }} shifts">
                    <tbody>
                    @foreach ($byDay[$weekday] as $shift)
                        <tr>
                            <td>{{ $shift['user_name'] }} <span class="muted small">{{ $shift['role'] }}</span></td>
                            <td>{{ $shift['department_name'] }}</td>
                            <td class="num">{{ substr($shift['starts'], 0, 5) }}–{{ substr($shift['ends'], 0, 5) }}</td>
                            <td class="actions">
                                <form method="POST" action="{{ route('settings.rota.destroy', $shift['id']) }}">
                                    @csrf @method('DELETE')
                                    <button type="submit" class="btn btn-small btn-danger" aria-label="Remove {{ $shift['user_name'] }} on {{ $name }}">Remove</button>
                                </form>
                            </td>
                        </tr>
                    @endforeach
                    </tbody>
                </table>
            @endif
        @endforeach
    </section>

    <section class="panel">
        <h2>Add shifts</h2>
        <form method="POST" action="{{ route('settings.rota.store') }}">
            @csrf
            <div class="field">
                <label for="user">Staff member</label>
                <select id="user" name="user" required>
                    <option value="">Choose…</option>
                    @foreach ($staff as $member)
                        <option value="{{ $member['id'] }}" @selected((int) old('user') === $member['id'])>
                            {{ $member['display_name'] ?: $member['username'] }} ({{ $member['role'] }})
                        </option>
                    @endforeach
                </select>
            </div>
            <div class="field">
                <label for="shift_department">Department</label>
                <select id="shift_department" name="department" required>
                    @foreach ($departments as $department)
                        <option value="{{ $department['id'] }}" @selected((int) old('department') === $department['id'])>{{ $department['name'] }}</option>
                    @endforeach
                </select>
            </div>
            <fieldset class="field">
                <legend>Days</legend>
                <div class="checks">
                    @foreach ($weekdays as $weekday => $name)
                        <label><input type="checkbox" name="weekdays[]" value="{{ $weekday }}"
                                      @checked(in_array((string) $weekday, (array) old('weekdays', []), true))> {{ substr($name, 0, 3) }}</label>
                    @endforeach
                </div>
            </fieldset>
            <div class="field-row">
                <div class="field"><label for="starts">From</label><input id="starts" name="starts" type="time" value="{{ old('starts', '08:00') }}" required></div>
                <div class="field"><label for="ends">To</label><input id="ends" name="ends" type="time" value="{{ old('ends', '16:00') }}" required></div>
            </div>
            <button type="submit" class="btn">Add shifts</button>
        </form>
    </section>
</div>
@endsection
