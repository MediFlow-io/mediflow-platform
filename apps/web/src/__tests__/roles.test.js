import { describe, expect, it } from "vitest";
import { actionsFor, can } from "../lib/roles";

const as = (role) => ({ role });

describe("can", () => {
  it("hides patient data from students and IT", () => {
    expect(can(as("student"), "readPatients")).toBe(false);
    expect(can(as("it"), "readPatients")).toBe(false);
    expect(can(as("lab"), "readPatients")).toBe(true);
  });
  it("only admins manage staff", () => {
    expect(can(as("admin"), "manageStaff")).toBe(true);
    expect(can(as("doctor"), "manageStaff")).toBe(false);
  });
  it("nurses can register but not edit patients (matches the server)", () => {
    expect(can(as("nurse"), "createPatients")).toBe(true);
    expect(can(as("nurse"), "editPatients")).toBe(false);
  });
  it("is false without a user", () => {
    expect(can(null, "dashboard")).toBe(false);
  });
});

describe("actionsFor", () => {
  const names = (role, status) => actionsFor(as(role), status).map((a) => a.name);
  it("offers only transitions valid for the status and role", () => {
    expect(names("reception", "waiting")).toEqual(["call", "cancel"]);
    expect(names("nurse", "waiting")).toEqual(["call", "start", "cancel"]);
    expect(names("doctor", "in_progress")).toEqual(["complete", "cancel"]);
    expect(names("reception", "in_progress")).toEqual(["cancel"]);
    expect(names("lab", "waiting")).toEqual([]);
    expect(names("doctor", "completed")).toEqual([]);
  });
});
