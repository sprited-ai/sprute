"""Quaternius UAL joint names mapped to Sprute body roles."""
QUATERNIUS = {'pelvis': 'Hips', 'spine_01': 'Spine', 'spine_02': 'Spine1',
              'spine_03': 'Spine2', 'neck_01': 'Neck', 'Head': 'Head'}
for short, side in [('l', 'Left'), ('r', 'Right')]:
    for source, role in [('clavicle', 'Shoulder'), ('upperarm', 'Arm'),
                         ('lowerarm', 'ForeArm'), ('hand', 'Hand'), ('thigh', 'UpLeg'),
                         ('calf', 'Leg'), ('foot', 'Foot'), ('ball', 'ToeBase')]:
        QUATERNIUS[f'{source}_{short}'] = side + role
