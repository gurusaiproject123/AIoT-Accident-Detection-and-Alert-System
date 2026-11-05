/** Staff -> one hospital; admin -> none; owner login -> one owner record -> many cars. */
export function validateUserAssignment(values, hospitals, owners = []) {
  const errors = {};
  if (!String(values.name ?? "").trim()) errors.name = "Name is required.";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(values.email ?? "").trim())) errors.email = "Enter a valid email address.";
  if (!["hospital_staff", "superuser", "car_owner"].includes(values.role)) errors.role = "Select a supported account role.";
  if (values.role === "hospital_staff" && !hospitals.some(h=>h.id===values.hospitalId)) errors.hospitalId = "Select this staff member's hospital.";
  if (values.role !== "hospital_staff" && values.hospitalId) errors.hospitalId = "Only hospital staff have a hospital assignment.";
  if (values.role === "car_owner") {
    const owner = owners.find(o=>o.id===values.ownerId);
    if (!owner || !owner.vehicleIds?.length) errors.ownerId = "Select a registered owner with at least one car.";
  } else if (values.ownerId) errors.ownerId = "Only car-owner logins link to an owner record.";
  return errors;
}
export function needsAssignmentCorrection(user,hospitals,owners=[]) {
  return Object.keys(validateUserAssignment(user,hospitals,owners)).length>0;
}
export function publicUserRecord(user) {
  return {id:user.id,name:String(user.name??""),email:String(user.email??""),role:user.role,
    hospitalId:user.hospitalId??null,ownerId:user.ownerId??null,status:user.status??"active",lastSignIn:user.lastSignIn??null};
}
export function canOpenSuperuser(user) {
  return user?.role === "superuser" && user?.status === "active" && user.hospitalId === null;
}
