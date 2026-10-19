@extends('layouts.app')
@section('title', 'Two-step sign-in')
@section('content')
<form method="POST" action="{{ url('/login/code') }}" class="card">
    @csrf
    <div class="brand"><span class="brand-mark"></span><span class="brand-name">MediFlow</span><span class="brand-tag">admin</span></div>
    <h1>Two-step sign-in</h1>
    <p class="subtitle">Enter the 6-digit code from your authenticator app.</p>
    @if ($errors->any())<div class="error-box" role="alert">{{ $errors->first() }}</div>@endif
    <div class="field">
        <label for="code">Authentication code</label>
        <input id="code" name="code" inputmode="numeric" autocomplete="one-time-code" maxlength="6" pattern="[0-9]{6}" required autofocus>
    </div>
    <button type="submit" class="btn">Verify</button>
    <p class="small"><a href="{{ route('login') }}">Use a different account</a></p>
</form>
@endsection
