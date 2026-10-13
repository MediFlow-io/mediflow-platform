package flow

import (
	"errors"
	"testing"
)

func status(err error) int {
	var fe *Error
	if errors.As(err, &fe) {
		return fe.Status
	}
	return 0
}

func TestTransitionsFollowTheLifecycle(t *testing.T) {
	cases := []struct {
		action, role string
		from         Status
		want         int // 0 = allowed
	}{
		{"call", Reception, Waiting, 0},
		{"call", Reception, Called, 409},
		{"start", Nurse, Waiting, 0},
		{"start", Nurse, Called, 0},
		{"start", Reception, Waiting, 403},
		{"complete", Doctor, InProgress, 0},
		{"complete", Doctor, Waiting, 409},
		{"cancel", Reception, InProgress, 0},
		{"cancel", Reception, Completed, 409},
		{"cancel", Student, Waiting, 403},
		{"call", Lab, Waiting, 403},
		{"teleport", Admin, Waiting, 404},
	}
	for _, c := range cases {
		_, err := Check(c.action, c.role, c.from)
		if got := status(err); got != c.want {
			t.Errorf("%s by %s from %s: got %d, want %d (%v)", c.action, c.role, c.from, got, c.want, err)
		}
	}
}

func TestTransitionTargetsAndTimestamps(t *testing.T) {
	want := map[string][2]string{
		"call": {"called", "called_at"}, "start": {"in_progress", "started_at"},
		"complete": {"completed", "completed_at"}, "cancel": {"cancelled", "completed_at"},
	}
	for action, w := range want {
		tr := Transitions[action]
		if string(tr.To) != w[0] || tr.Timestamp != w[1] {
			t.Errorf("%s: got %s/%s, want %s/%s", action, tr.To, tr.Timestamp, w[0], w[1])
		}
	}
}

func TestConflictMessageMatchesCoreAPI(t *testing.T) {
	_, err := Check("complete", Doctor, Waiting)
	if err.Error() != "Cannot complete a visit that is waiting." {
		t.Fatalf("unexpected message %q", err)
	}
	_, err = Check("cancel", Admin, InProgress)
	if err != nil {
		t.Fatal(err)
	}
	_, err = Check("call", Admin, InProgress)
	if err.Error() != "Cannot call a visit that is in progress." {
		t.Fatalf("unexpected message %q", err)
	}
}

func TestPermissions(t *testing.T) {
	if CanReadVisits(Student) || CanReadVisits(IT) || !CanReadVisits(Pharmacy) {
		t.Error("visit read permissions wrong")
	}
	if !CanCheckIn(Nurse) || CanCheckIn(Lab) {
		t.Error("check-in permissions wrong")
	}
	if CanEditVisit(Nurse) || !CanEditVisit(Reception) {
		t.Error("edit permissions wrong (nurses check in and start/complete, but don't edit)")
	}
	if !CanSeeDashboard(IT) || CanSeeDashboard(Student) {
		t.Error("dashboard permissions wrong")
	}
}

func TestESIAndActive(t *testing.T) {
	for esi, ok := range map[int]bool{0: false, 1: true, 5: true, 6: false} {
		if ValidESI(esi) != ok {
			t.Errorf("ValidESI(%d) != %v", esi, ok)
		}
	}
	if !Called.IsActive() || Completed.IsActive() {
		t.Error("IsActive wrong")
	}
}
