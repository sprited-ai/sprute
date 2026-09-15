"""Prepare reviewed reference + projected motion metadata for the external renderer."""
import argparse
import hashlib
import json
from pathlib import Path

from rig_conditioning import fit_body, prepare_metadata


def prepare(reference_path, motion_path, output, *, fit_policy, head_policy,
            vertical_lift, cycle_frames=32):
    reference_path, motion_path, output = map(Path, (reference_path, motion_path, output))
    reference_bytes, motion_bytes = reference_path.read_bytes(), motion_path.read_bytes()
    reference = json.loads(reference_bytes)
    motion = json.loads(motion_bytes)
    body, fit = fit_body(reference['keypoints_body'],
                         [row['keypoints_body'] for row in motion['rows']],
                         fit_policy=fit_policy, vertical_lift=vertical_lift,
                         cycle_frames=cycle_frames)
    ref, rows = prepare_metadata(reference, body, head_policy=head_policy)
    fitted = {'reference': ref, 'rows': rows, 'fit': fit, 'visibility': head_policy}
    receipt = {
        'referenceSha256': hashlib.sha256(reference_bytes).hexdigest(),
        'motionSha256': hashlib.sha256(motion_bytes).hexdigest(),
        'frames': len(rows), 'fitPolicy': fit_policy, 'headPolicy': head_policy,
        'verticalLift': vertical_lift, 'cycleFrames': cycle_frames,
        'scope': 'Metadata preparation only; reference anatomy and generated quality require review',
    }
    # Validate and serialize before claiming output. Existing runs are never overwritten.
    payload = json.dumps(fitted, indent=2, allow_nan=False) + '\n'
    receipt['fittedSha256'] = hashlib.sha256(payload.encode()).hexdigest()
    receipt_payload = json.dumps(receipt, indent=2, allow_nan=False) + '\n'
    output.mkdir(parents=False, exist_ok=False)
    (output / 'fitted.json').write_text(payload)
    (output / 'preparation.json').write_text(receipt_payload)
    return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference', type=Path, required=True, help='Reviewed reference metadata JSON')
    p.add_argument('--motion', type=Path, required=True, help='JSON containing projected body metadata rows')
    p.add_argument('--output', type=Path, required=True, help='New output directory; parent must exist')
    p.add_argument('--fit', choices=['shoulder-width', 'uniform-envelope'], required=True)
    p.add_argument('--head', choices=['reference-head', 'hidden-head'], required=True)
    p.add_argument('--vertical-lift', type=float, required=True)
    p.add_argument('--cycle-frames', type=int, default=32)
    a = p.parse_args()
    try:
        receipt = prepare(a.reference, a.motion, a.output, fit_policy=a.fit,
                          head_policy=a.head, vertical_lift=a.vertical_lift,
                          cycle_frames=a.cycle_frames)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        p.exit(2, f'Preparation failed: {exc}\n')
    print(f"Prepared {receipt['frames']} frames: {a.output / 'fitted.json'}")


if __name__ == '__main__':
    main()
