@extends('layouts.app')
@section('title', 'Departments')
@section('content')
<header class="page-header">
    <div>
        <h1>Departments</h1>
        <p class="subtitle">Departments patients can be checked into. Closing one blocks new check-ins; patients already in its queue are not affected.</p>
    </div>
</header>

<div class="split">
    <section class="panel">
        <h2>All departments</h2>
        <table class="table">
            <thead><tr><th>Name</th><th>Code</th><th>Status</th><th></th></tr></thead>
            <tbody>
            @foreach ($departments as $department)
                <tr class="{{ $department['active'] ? '' : 'row-muted' }}">
                    <td>{{ $department['name'] }}</td>
                    <td><code>{{ $department['code'] }}</code></td>
                    <td><span class="badge {{ $department['active'] ? 'badge-ok' : 'badge-off' }}">{{ $department['active'] ? 'Open' : 'Closed' }}</span></td>
                    <td class="actions">
                        <form method="POST" action="{{ route('departments.update', $department['id']) }}">
                            @csrf @method('PATCH')
                            <input type="hidden" name="active" value="{{ $department['active'] ? 0 : 1 }}">
                            <button type="submit" class="btn btn-small {{ $department['active'] ? 'btn-danger' : 'btn-secondary' }}">
                                {{ $department['active'] ? 'Close' : 'Reopen' }}
                            </button>
                        </form>
                    </td>
                </tr>
            @endforeach
            </tbody>
        </table>
    </section>
    <section class="panel">
        <h2>Add a department</h2>
        <form method="POST" action="{{ route('departments.store') }}">
            @csrf
            @if ($errors->any())<div class="error-box" role="alert">{{ $errors->first() }}</div>@endif
            <div class="field"><label for="name">Name</label><input id="name" name="name" value="{{ old('name') }}" required maxlength="100" placeholder="Dental Clinic"></div>
            <div class="field"><label for="code">Code</label><input id="code" name="code" value="{{ old('code') }}" required maxlength="24" placeholder="dental"></div>
            <button type="submit" class="btn">Add department</button>
        </form>
    </section>
</div>
@endsection
