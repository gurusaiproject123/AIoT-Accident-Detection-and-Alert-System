export const ROLE_HOME = Object.freeze({ hospital_staff: '/hospital', superuser: '/superuser', car_owner: '/vehicle' });

/** The input MUST come from verified FastAPI /api/auth/me, never signup metadata. */
export function normalizeVerifiedProfile(raw, sessionUserId) {
  if (!raw || raw.id !== sessionUserId || !sessionUserId) throw new Error('Account identity could not be verified.');
  if (!Object.hasOwn(ROLE_HOME, raw.role)) throw new Error('This account has no supported system role. Contact the administrator.');
  if (raw.status !== 'active') throw new Error('This account is suspended or inactive. Contact the administrator.');
  if (raw.hospital_id !== null && (typeof raw.hospital_id !== 'string' || !raw.hospital_id.trim())) {
    throw new Error('The hospital assignment is missing or invalid.');
  }
  if (raw.role === 'hospital_staff' && !raw.hospital_id) throw new Error('Hospital staff must be assigned to one hospital.');
  if (raw.role !== 'hospital_staff' && raw.hospital_id !== null) throw new Error('This account must not have a hospital assignment.');
  const ownerId = raw.owner_id ?? null;
  if (raw.role === 'car_owner' && (typeof ownerId !== 'string' || !ownerId.trim())) {
    throw new Error('This owner account is not linked to a registered car owner. Contact the administrator.');
  }
  if (raw.role !== 'car_owner' && ownerId !== null) throw new Error('The owner assignment does not match this account role.');
  return Object.freeze({ id:raw.id, name:raw.full_name ?? '', role:raw.role, status:raw.status,
    hospitalId:raw.hospital_id, ownerId });
}
export function homeForProfile(profile) { return ROLE_HOME[profile?.role] ?? '/login'; }
