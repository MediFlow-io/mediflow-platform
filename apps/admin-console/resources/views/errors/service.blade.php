@extends('layouts.app')
@section('title', 'Problem')
@section('content')
<div class="{{ isset($adminUser) ? 'panel narrow' : 'card' }}">
    <h1>Something went wrong</h1>
    <div class="error-box" role="alert">{{ $message }}</div>
    <p><a class="btn btn-secondary" href="{{ url()->previous() }}">Go back</a></p>
</div>
@endsection
