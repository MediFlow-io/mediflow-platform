@extends('layouts.app')
@section('title', 'Sign in')
@section('content')
<form method="POST" action="{{ url('/login') }}" class="card">
    @csrf
    <div class="brand"><span class="brand-mark"></span><span class="brand-name">MediFlow</span><span class="brand-tag">admin</span></div>
    <h1>Admin console</h1>
    <p class="subtitle">Audit log, flow reports and department settings. Administrators only.</p>
    @if (session('status'))<div class="success-box" role="status">{{ session('status') }}</div>@endif
    @if ($errors->any())<div class="error-box" role="alert">{{ $errors->first() }}</div>@endif
    <div class="field">
        <label for="username">Staff ID</label>
        <input id="username" name="username" value="{{ old('username') }}" required autocomplete="username" autofocus>
    </div>
    <div class="field">
        <label for="password">Password</label>
        <input id="password" name="password" type="password" required autocomplete="current-password">
    </div>
    <button type="submit" class="btn">Sign in</button>
</form>
@endsection
