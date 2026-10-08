"""Explicit source-joint to humanoid-role mappings; never infer a vendor from a filename."""
MIXAMO_PREFIXES = ('mixamorig:', 'mixamorig_', 'mixamorig')
QUATERNIUS = {'pelvis': 'Hips', 'spine_01': 'Spine', 'spine_02': 'Spine1',
              'spine_03': 'Spine2', 'neck_01': 'Neck', 'Head': 'Head'}
for short, side in [('l', 'Left'), ('r', 'Right')]:
    for source, role in [('clavicle', 'Shoulder'), ('upperarm', 'Arm'),
                         ('lowerarm', 'ForeArm'), ('hand', 'Hand'), ('thigh', 'UpLeg'),
                         ('calf', 'Leg'), ('foot', 'Foot'), ('ball', 'ToeBase')]:
        QUATERNIUS[f'{source}_{short}'] = side + role


def roles(names, explicit=None):
    """Return profile and source-name -> role. Explicit mappings supplement no guesses."""
    if explicit is not None:
        if not isinstance(explicit, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in explicit.items()):
            raise ValueError('Mapping must be a JSON object of source joint names to humanoid roles')
        unknown = set(explicit.values()) - set(QUATERNIUS.values())
        if unknown:
            raise ValueError(f'Unknown humanoid roles: {sorted(unknown)}')
        missing = set(explicit) - set(names)
        if missing:
            raise ValueError(f'Mapping references absent source joints: {sorted(missing)}')
        if len(set(explicit.values())) != len(explicit):
            raise ValueError('Each humanoid role must map to exactly one source joint')
        return 'custom', dict(explicit)
    if set(QUATERNIUS) <= set(names):
        return 'quaternius', dict(QUATERNIUS)
    mapped = {}
    for name in names:
        role = name
        for prefix in MIXAMO_PREFIXES:
            role = role.removeprefix(prefix)
        mapped[name] = role
    return 'mixamo-compatible', mapped
