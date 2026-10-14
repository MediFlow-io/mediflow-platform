<?php

namespace App\Http\Controllers;

use App\Exceptions\MediflowException;
use App\Services\MediflowClient;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\View\View;

/** Department settings. Departments are owned by the core API; this screen edits them through its API. */
class DepartmentController extends Controller
{
    public function index(MediflowClient $mediflow): View
    {
        return view('departments.index', ['departments' => $mediflow->departments()]);
    }

    public function store(Request $request, MediflowClient $mediflow): RedirectResponse
    {
        $data = $request->validate([
            'name' => ['required', 'string', 'max:100'],
            'code' => ['required', 'string', 'max:24', 'regex:/^[a-z0-9-]+$/'],
        ], ['code.regex' => 'Use lowercase letters, numbers and dashes only (e.g. "dental").']);
        try {
            $created = $mediflow->createDepartment($data + ['active' => true]);
        } catch (MediflowException $e) {
            if ($e->status !== 400) {
                throw $e;
            }

            return back()->withInput()->withErrors($e->errors ?: ['name' => $e->getMessage()]);
        }

        return redirect()->route('departments')->with('status', "Department “{$created['name']}” created.");
    }

    public function update(int $id, Request $request, MediflowClient $mediflow): RedirectResponse
    {
        $data = $request->validate(['active' => ['required', 'boolean']]);
        $updated = $mediflow->updateDepartment($id, ['active' => (bool) $data['active']]);
        $state = $updated['active'] ? 'reopened' : 'closed: new check-ins are blocked';

        return redirect()->route('departments')->with('status', "“{$updated['name']}” {$state}.");
    }
}
