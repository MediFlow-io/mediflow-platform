package api

import (
	"encoding/json"
	"fmt"
	"strings"

	"mediflow/patient-flow/internal/store"
)

// vitalsJSON is how vitals appear in requests and responses. It's the same shape the AI triage
// endpoint takes, so the check-in form can send one payload to both.
type vitalsJSON struct {
	HeartRate    *int     `json:"heart_rate"`
	RespRate     *int     `json:"resp_rate"`
	SpO2         *int     `json:"spo2"`
	TemperatureC *float64 `json:"temperature_c"`
	SystolicBP   *int     `json:"systolic_bp"`
	AVPU         string   `json:"avpu"`
}

// Plausible ranges, matching the AI service's request schema.
var vitalRanges = []struct {
	name     string
	min, max float64
	get      func(v vitalsJSON) *float64
}{
	{"heart_rate", 0, 300, func(v vitalsJSON) *float64 { return intPtrToFloat(v.HeartRate) }},
	{"resp_rate", 0, 100, func(v vitalsJSON) *float64 { return intPtrToFloat(v.RespRate) }},
	{"spo2", 0, 100, func(v vitalsJSON) *float64 { return intPtrToFloat(v.SpO2) }},
	{"temperature_c", 25, 45, func(v vitalsJSON) *float64 { return v.TemperatureC }},
	{"systolic_bp", 0, 300, func(v vitalsJSON) *float64 { return intPtrToFloat(v.SystolicBP) }},
}

func intPtrToFloat(i *int) *float64 {
	if i == nil {
		return nil
	}
	f := float64(*i)
	return &f
}

// parseVitals reads chief_complaint, pain_score and vitals from a request. present reports whether
// any of the three keys was sent (PATCH replaces the whole set only when one is).
func parseVitals(fields map[string]json.RawMessage, problems store.ValidationError) (v store.Vitals, present bool) {
	if raw, ok := fields["chief_complaint"]; ok {
		present = true
		if string(raw) != "null" && json.Unmarshal(raw, &v.Complaint) != nil {
			problems["chief_complaint"] = []string{"Not a valid string."}
		}
		v.Complaint = strings.TrimSpace(v.Complaint)
		if len([]rune(v.Complaint)) > 500 {
			problems["chief_complaint"] = []string{"Ensure this field has no more than 500 characters."}
		}
	}
	if raw, ok := fields["pain_score"]; ok {
		present = true
		if string(raw) != "null" {
			var pain int
			if json.Unmarshal(raw, &pain) != nil || pain < 0 || pain > 10 {
				problems["pain_score"] = []string{"Pain score must be a whole number from 0 to 10."}
			} else {
				v.PainScore = &pain
			}
		}
	}
	if raw, ok := fields["vitals"]; ok {
		present = true
		if string(raw) == "null" {
			return v, present
		}
		var in vitalsJSON
		dec := json.NewDecoder(strings.NewReader(string(raw)))
		dec.DisallowUnknownFields()
		if err := dec.Decode(&in); err != nil {
			problems["vitals"] = []string{"Vitals must be an object with heart_rate, resp_rate, spo2, temperature_c, systolic_bp and avpu."}
			return v, present
		}
		for _, r := range vitalRanges {
			if val := r.get(in); val != nil && (*val < r.min || *val > r.max) {
				problems["vitals."+r.name] = []string{fmt.Sprintf("Must be between %g and %g.", r.min, r.max)}
			}
		}
		switch in.AVPU {
		case "", "A", "V", "P", "U":
		default:
			problems["vitals.avpu"] = []string{"Must be A, V, P or U."}
		}
		v.HeartRate, v.RespRate, v.SpO2, v.TemperatureC, v.SystolicBP, v.AVPU =
			in.HeartRate, in.RespRate, in.SpO2, in.TemperatureC, in.SystolicBP, in.AVPU
	}
	return v, present
}

func vitalsOut(v store.Vitals) vitalsJSON {
	return vitalsJSON{HeartRate: v.HeartRate, RespRate: v.RespRate, SpO2: v.SpO2, TemperatureC: v.TemperatureC,
		SystolicBP: v.SystolicBP, AVPU: v.AVPU}
}
