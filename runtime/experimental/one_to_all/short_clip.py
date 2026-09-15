"""Experimental adapter for valid short clips; not installed in upstream runtime."""
def split_plan(frame_count, upstream):
    if not isinstance(frame_count, int) or isinstance(frame_count, bool) or frame_count < 65 or frame_count % 4 != 1:
        raise ValueError('Expected at least 65 frames, with length 4k+1')
    if frame_count <= 81:
        return [(0, frame_count)]
    return upstream(frame_count)
