package api

import (
	"encoding/json"
	"testing"

	"mediflow/patient-flow/internal/store"
)

func TestCheckInStoresVitals(t *testing.T) {
	f, s := newFixture()
	rec, _ := call(t, s.Routes(), "POST", "/api/visits", "user-6", `{"patient": 7, "department": 1, "esi": 2,
		"chief_complaint": "  chest pain  ", "pain_score": 6,
		"vitals": {"heart_rate": 112, "spo2": 95, "temperature_c": 37.4, "avpu": "A"}}`)
	if rec.Code != 201 {
		t.Fatalf("status %d: %s", rec.Code, rec.Body)
	}
	v := f.gotCheckIn.Vitals
	if v.Complaint != "chest pain" || *v.PainScore != 6 || *v.HeartRate != 112 || *v.SpO2 != 95 || *v.TemperatureC != 37.4 || v.AVPU != "A" || v.RespRate != nil {
		t.Fatalf("vitals not parsed: %+v", v)
	}
}

func TestVitalsValidation(t *testing.T) {
	_, s := newFixture()
	h := s.Routes()
	cases := map[string]string{
		`{"vitals": {"spo2": 150}}`:         "vitals.spo2",
		`{"vitals": {"temperature_c": 12}}`: "vitals.temperature_c",
		`{"vitals": {"avpu": "X"}}`:         "vitals.avpu",
		`{"vitals": {"pulse": 80}}`:         "vitals",
		`{"pain_score": 11}`:                "pain_score",
		`{"chief_complaint": 42}`:           "chief_complaint",
	}
	for extra, field := range cases {
		body := `{"patient": 7, "department": 1, "esi": 3, ` + extra[1:]
		rec, got := call(t, h, "POST", "/api/visits", "user-6", body)
		if rec.Code != 400 || got[field] == nil {
			t.Errorf("%s: want 400 with %q error, got %d %v", extra, field, rec.Code, got)
		}
	}
}

func TestVisitJSONIncludesVitals(t *testing.T) {
	f, s := newFixture()
	hr, pain := 88, 2
	f.visits[0].Vitals = store.Vitals{Complaint: "cough", PainScore: &pain, HeartRate: &hr, AVPU: "A"}
	rec, _ := call(t, s.Routes(), "GET", "/api/visits/10", "user-1", "")
	var got struct {
		Complaint string         `json:"chief_complaint"`
		Pain      *int           `json:"pain_score"`
		Vitals    map[string]any `json:"vitals"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatal(err)
	}
	if got.Complaint != "cough" || *got.Pain != 2 || got.Vitals["heart_rate"] != 88.0 || got.Vitals["spo2"] != nil || got.Vitals["avpu"] != "A" {
		t.Fatalf("unexpected vitals JSON: %s", rec.Body)
	}
}

func TestPatchReplacesVitalsOnlyWhenSent(t *testing.T) {
	f, s := newFixture()
	h := s.Routes()
	call(t, h, "PATCH", "/api/visits/10", "user-6", `{"esi": 2}`)
	if f.gotPatch.Vitals != nil {
		t.Fatal("vitals must be untouched when not sent")
	}
	call(t, h, "PATCH", "/api/visits/10", "user-6", `{"vitals": {"heart_rate": 70}}`)
	if f.gotPatch.Vitals == nil || *f.gotPatch.Vitals.HeartRate != 70 {
		t.Fatalf("vitals should be replaced: %+v", f.gotPatch.Vitals)
	}
}
