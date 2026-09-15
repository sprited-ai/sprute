/** Portable Godot demo files; all assets remain beside the generated scene. */
export function godotDemoFiles(cellWidth: number, cellHeight: number): Record<string, string> {
  const scale = 128 / Math.max(cellWidth, cellHeight);
  return {
    "project.godot": `config_version=5

[application]
config/name="Sprute — Walk Demo"
run/main_scene="res://main.tscn"

[display]
window/size/viewport_width=720
window/size/viewport_height=480
window/size/window_width_override=1440
window/size/window_height_override=960
window/size/resizable=true
window/stretch/mode="canvas_items"
window/stretch/aspect="keep"

[rendering]
renderer/rendering_method="gl_compatibility"
textures/default_filters/use_nearest_mipmap_filter=false
`,
    "player.gd": `extends Node2D

const DIRECTIONS = ["S", "SE", "E", "NE", "N", "NW", "W", "SW"]
const SPEED = 120.0
var was_moving = false
@onready var sprite: AnimatedSprite2D = $Character

func _process(delta: float) -> void:
	var movement = Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
	if movement.is_zero_approx():
		sprite.pause()
		was_moving = false
		return
	position += movement * SPEED * delta
	position = position.clamp(Vector2(64, 112), get_viewport_rect().size - Vector2(64, 64))
	var direction = posmod(roundi(atan2(movement.x, movement.y) / (TAU / 8.0)), 8)
	var next_animation: String = DIRECTIONS[direction]
	if sprite.animation != next_animation:
		# Keep playback position when changing direction; generated gait phase may differ.
		var previous_frame = sprite.frame
		var previous_progress = sprite.frame_progress
		sprite.play(next_animation)
		sprite.set_frame_and_progress(previous_frame, previous_progress)
	elif not was_moving:
		sprite.play()
	was_moving = true
`,
    "main.tscn": `[gd_scene load_steps=3 format=3]

[ext_resource type="Script" path="res://player.gd" id="1"]
[ext_resource type="SpriteFrames" path="res://walk.tres" id="2"]

[node name="WalkDemo" type="Node2D"]

[node name="Background" type="Polygon2D" parent="."]
polygon = PackedVector2Array(0, 0, 720, 0, 720, 480, 0, 480)
color = Color(0.12, 0.15, 0.19, 1)

[node name="Instructions" type="Label" parent="."]
offset_left = 24.0
offset_top = 20.0
offset_right = 680.0
offset_bottom = 65.0
text = "Use the arrow keys to walk.\nHold two arrows to move diagonally."

[node name="Player" type="Node2D" parent="."]
position = Vector2(360, 260)
script = ExtResource("1")

[node name="Character" type="AnimatedSprite2D" parent="Player"]
texture_filter = 1
sprite_frames = ExtResource("2")
animation = &"S"
`.replace('texture_filter = 1', `texture_filter = 1\nscale = Vector2(${scale}, ${scale})`),
  };
}
