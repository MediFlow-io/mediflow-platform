<?php

namespace App\Http\Controllers;

use App\Exceptions\MediflowException;
use App\Services\MediflowClient;
use Illuminate\View\View;

/** Expected waits per department and where patient flow gets stuck (decision support, from the AI service). */
class InsightsController extends Controller
{
    public function __invoke(MediflowClient $mediflow): View
    {
        try {
            return view('insights.index', ['insights' => $mediflow->insights(), 'error' => null]);
        } catch (MediflowException $e) {
            if ($e->status !== 503) {
                throw $e;
            }

            return view('insights.index', ['insights' => null, 'error' => $e->getMessage()]);
        }
    }
}
