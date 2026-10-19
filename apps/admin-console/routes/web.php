<?php

use App\Http\Controllers\AuditController;
use App\Http\Controllers\AuthController;
use App\Http\Controllers\DashboardController;
use App\Http\Controllers\DepartmentController;
use App\Http\Controllers\ReportController;
use App\Http\Controllers\SettingsController;
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
    Route::get('/settings', [SettingsController::class, 'index'])->name('settings');
    Route::post('/settings/queue', [SettingsController::class, 'saveQueue'])->name('settings.queue');
    Route::post('/settings/holidays', [SettingsController::class, 'addHoliday'])->name('settings.holidays.store');
    Route::delete('/settings/holidays/{id}', [SettingsController::class, 'removeHoliday'])->whereNumber('id')->name('settings.holidays.destroy');
    Route::get('/settings/hours', [SettingsController::class, 'hours'])->name('settings.hours');
    Route::post('/settings/hours', [SettingsController::class, 'saveHours'])->name('settings.hours.save');
    Route::get('/settings/rota', [SettingsController::class, 'rota'])->name('settings.rota');
    Route::post('/settings/rota', [SettingsController::class, 'addShift'])->name('settings.rota.store');
    Route::delete('/settings/rota/{id}', [SettingsController::class, 'removeShift'])->whereNumber('id')->name('settings.rota.destroy');
});
