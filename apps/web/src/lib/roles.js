// What each role may do in the UI. These mirror the server's rules (apps/core-api: accounts/permissions.py
// and patients/flow.py) only to hide buttons people can't use. The server always enforces them.
const sets = {
  readPatients: ["admin", "doctor", "nurse", "reception", "lab", "pharmacy"],
  createPatients: ["admin", "doctor", "nurse", "reception"],
  editPatients: ["admin", "doctor", "reception"],
  checkIn: ["admin", "doctor", "nurse", "reception"],
  triageSuggestion: ["admin", "doctor", "nurse"],
  changeTriage: ["admin", "doctor", "nurse"],
  readRecord: ["admin", "doctor", "nurse"],
  writeNotes: ["doctor", "nurse"],
  prescribe: ["doctor"],
  admit: ["doctor", "nurse"],
  pharmacy: ["pharmacy"],
  manageStaff: ["admin"],
  manageAppointments: ["admin", "doctor", "nurse", "reception"],
  dashboard: ["admin", "doctor", "nurse", "reception", "lab", "pharmacy", "it"],
};

export const VISIT_ACTIONS = {
  call: { label: "Call", roles: ["admin", "doctor", "nurse", "reception"], from: ["waiting"] },
  start: { label: "Start consultation", roles: ["admin", "doctor", "nurse"], from: ["waiting", "called"] },
  complete: { label: "Complete", roles: ["admin", "doctor", "nurse"], from: ["in_progress"] },
  cancel: { label: "Cancel", roles: ["admin", "doctor", "nurse", "reception"], from: ["waiting", "called", "in_progress"] },
};

export const STAFF_ROLES = ["admin", "doctor", "nurse", "reception", "lab", "pharmacy", "it"];

export function can(user, permission) {
  return Boolean(user && sets[permission]?.includes(user.role));
}

export function actionsFor(user, status) {
  return Object.entries(VISIT_ACTIONS)
    .filter(([, a]) => user && a.roles.includes(user.role) && a.from.includes(status))
    .map(([name, a]) => ({ name, label: a.label }));
}
