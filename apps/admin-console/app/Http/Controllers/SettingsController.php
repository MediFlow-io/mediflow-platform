<?php

namespace App\Http\Controllers;

use App\Exceptions\MediflowException;
use App\Services\MediflowClient;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\View\View;

/**
 * Clinic settings: queue rules, holidays, opening hours and the staff rota.
 * The data is stored by the core API (apps/core-api/apps/clinic); this console only edits it.
 */
class SettingsController extends Controller
{
    public const WEEKDAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

    private const QUEUE_FIELDS = [
        'esi1_target_minutes', 'esi2_target_minutes', 'esi3_target_minutes', 'esi4_target_minutes', 'esi5_target_minutes',
        'long_wait_minutes', 'turn_near_ahead', 'slot_minutes', 'max_days_ahead', 'min_notice_minutes', 'max_open_appointments',
    ];

    // ---------------------------------------------------------------- queue rules and holidays

    public function index(MediflowClient $mediflow): View
    {
        return view('settings.index', [
            'queue' => $mediflow->queueSettings(),
            'holidays' => $mediflow->holidays(true),
        ]);
    }

    public function saveQueue(Request $request, MediflowClient $mediflow): RedirectResponse
    {
        $rules = array_fill_keys(self::QUEUE_FIELDS, ['required', 'integer', 'min:0', 'max:1440']);
        $rules['slot_minutes'] = ['required', 'integer', 'in:5,10,15,20,30,60'];
        $rules['max_days_ahead'] = ['required', 'integer', 'min:1', 'max:365'];
        $rules['max_open_appointments'] = ['required', 'integer', 'min:1', 'max:20'];
        $data = array_map('intval', $request->validate($rules));

        return $this->attempt(fn () => $mediflow->updateQueueSettings($data), 'settings', 'Queue rules saved.');
    }

    public function addHoliday(Request $request, MediflowClient $mediflow): RedirectResponse
    {
        $data = $request->validate([
            'date' => ['required', 'date_format:Y-m-d', 'after_or_equal:today'],
            'name' => ['required', 'string', 'max:100'],
        ], ['date.after_or_equal' => 'Choose today or a later date.']);

        return $this->attempt(fn () => $mediflow->addHoliday($data), 'settings',
            "Holiday added: {$data['name']} ({$data['date']}). No appointments can be booked that day.");
    }

    public function removeHoliday(int $id, MediflowClient $mediflow): RedirectResponse
    {
        $mediflow->removeHoliday($id);

        return redirect()->route('settings')->with('status', 'Holiday removed.');
    }

    // ---------------------------------------------------------------- opening hours

    public function hours(Request $request, MediflowClient $mediflow): View
    {
        $departments = $mediflow->departments();
        $selected = $request->integer('department') ?: null;
        $all = $mediflow->hours();
        $mine = array_values(array_filter($all, fn ($h) => ($h['department'] ?? null) === $selected));
        $defaults = array_values(array_filter($all, fn ($h) => ($h['department'] ?? null) === null));
        $byDay = [];
        foreach ($mine as $h) {
            $byDay[$h['weekday']] = $h;
        }

        return view('settings.hours', [
            'departments' => $departments,
            'selected' => $selected,
            'byDay' => $byDay,
            'usesDefault' => $selected !== null && $mine === [],
            'hasDefault' => $defaults !== [],
            'weekdays' => self::WEEKDAYS,
        ]);
    }

    public function saveHours(Request $request, MediflowClient $mediflow): RedirectResponse
    {
        $request->validate([
            'department' => ['nullable', 'integer'],
            'days' => ['array'],
            'days.*.open' => ['nullable', 'boolean'],
            'days.*.opens' => ['nullable', 'date_format:H:i'],
            'days.*.closes' => ['nullable', 'date_format:H:i'],
        ]);
        $department = $request->integer('department') ?: null;
        $days = [];
        $errors = [];
        foreach (self::WEEKDAYS as $weekday => $name) {
            $day = $request->input("days.$weekday", []);
            if (empty($day['open'])) {
                continue;
            }
            if (empty($day['opens']) || empty($day['closes']) || $day['closes'] <= $day['opens']) {
                $errors["days.$weekday"] = "$name: give an opening time and a later closing time.";
                continue;
            }
            $days[] = ['weekday' => $weekday, 'opens' => $day['opens'], 'closes' => $day['closes']];
        }
        if ($errors) {
            return back()->withInput()->withErrors($errors);
        }
        $redirect = redirect()->route('settings.hours', array_filter(['department' => $department]));
        try {
            $mediflow->putHours($department, $days);
        } catch (MediflowException $e) {
            if ($e->status !== 400) {
                throw $e;
            }

            return back()->withInput()->withErrors(['days' => $e->getMessage()]);
        }
        $message = match (true) {
            $department !== null && $days === [] => 'This department now uses the clinic’s default hours.',
            $days === [] => 'Default hours cleared: appointments use the fallback hours until you set them.',
            default => 'Opening hours saved.',
        };

        return $redirect->with('status', $message);
    }

    // ---------------------------------------------------------------- staff rota

    public function rota(Request $request, MediflowClient $mediflow): View
    {
        $shifts = $mediflow->shifts();
        $byDay = array_fill(0, 7, []);
        foreach ($shifts as $shift) {
            $byDay[$shift['weekday']][] = $shift;
        }

        return view('settings.rota', [
            'byDay' => $byDay,
            'staff' => $mediflow->activeStaff(),
            'departments' => array_values(array_filter($mediflow->departments(), fn ($d) => $d['active'])),
            'weekdays' => self::WEEKDAYS,
        ]);
    }

    public function addShift(Request $request, MediflowClient $mediflow): RedirectResponse
    {
        $data = $request->validate([
            'user' => ['required', 'integer'],
            'department' => ['required', 'integer'],
            'weekdays' => ['required', 'array', 'min:1'],
            'weekdays.*' => ['integer', 'between:0,6'],
            'starts' => ['required', 'date_format:H:i'],
            'ends' => ['required', 'date_format:H:i', 'after:starts'],
        ], ['weekdays.required' => 'Tick at least one day.', 'ends.after' => 'The shift must end after it starts.']);
        try {
            foreach (array_unique($data['weekdays']) as $weekday) {
                $mediflow->addShift(['user' => (int) $data['user'], 'department' => (int) $data['department'],
                    'weekday' => (int) $weekday, 'starts' => $data['starts'], 'ends' => $data['ends']]);
            }
        } catch (MediflowException $e) {
            if ($e->status !== 400) {
                throw $e;
            }

            return back()->withInput()->withErrors(['user' => $e->getMessage()]);
        }
        $count = count(array_unique($data['weekdays']));

        return redirect()->route('settings.rota')->with('status', $count === 1 ? 'Shift added.' : "$count shifts added.");
    }

    public function removeShift(int $id, MediflowClient $mediflow): RedirectResponse
    {
        $mediflow->removeShift($id);

        return redirect()->route('settings.rota')->with('status', 'Shift removed.');
    }

    // ---------------------------------------------------------------- helpers

    private function attempt(callable $call, string $route, string $message): RedirectResponse
    {
        try {
            $call();
        } catch (MediflowException $e) {
            if ($e->status !== 400) {
                throw $e;
            }

            return back()->withInput()->withErrors($e->errors ?: ['form' => $e->getMessage()]);
        }

        return redirect()->route($route)->with('status', $message);
    }
}
