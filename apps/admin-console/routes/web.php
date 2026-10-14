<?php

use App\Http\Controllers\AuditController;
use App\Http\Controllers\AuthController;
use App\Http\Controllers\DashboardController;
use App\Http\Controllers\DepartmentController;
use App\Http\Controllers\ReportController;
use Illuminate\Support\Facades\Route;

Route::get('/login', [AuthController::class, 'show'])->name('login');
Route::post('/login', [AuthController::class, 'login'])->middleware('throttle:10,1');

Route::middleware('admin')->group(function () {
    Route::get('/', DashboardController::class)->name('dashboard');
    Route::post('/logout', [AuthController::class, 'logout'])->name('logout');
    Route::get('/audit', [AuditController::class, 'index'])->name('audit');
    Route::get('/reports', [ReportController::class, 'index'])->name('reports');
    Route::get('/reports/flow.csv', [ReportController::class, 'csv'])->name('reports.csv');
    Route::get('/departments', [DepartmentController::class, 'index'])->name('departments');
    Route::post('/departments', [DepartmentController::class, 'store'])->name('departments.store');
    Route::patch('/departments/{id}', [DepartmentController::class, 'update'])->whereNumber('id')->name('departments.update');
});
