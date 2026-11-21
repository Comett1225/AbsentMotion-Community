# Effects

Effects people made for [AbsentMotion](https://github.com/Comett1225/AbsentMotion). Each folder holds one effect (`.json`) or a pack of effects (`.amfx`).

## Using an effect

- In the app, open **Home > Community > Effects**, tap an effect, and tap **Add**.
- Or download the file and open it with AbsentMotion on a phone, or drop it on the AbsentMotion window on a computer.

The app shows a preview and checks that the effect works on your device before adding it. Added effects are in **Effects > Added** and work like any other effect.

An added effect is only a shader and its settings. It can't read your files or go online.

## Making your own effect

An effect is a small text file. It lists the effect's settings and holds a **shader**, a short program that works out the color of every pixel of the layer. Shaders are written in SkSL, the shading language of the Skia graphics library that AbsentMotion draws with. SkSL looks like GLSL.

### Example

Save this as `simple-duotone.json`:

```json
{
  "id": "simple-duotone",
  "name": "Simple Duotone",
  "category": "color",
  "description": "Turns dark parts into one color and bright parts into another.",
  "author": "Your name",
  "licence": "CC BY 4.0",
  "version": 1,
  "params": [
    {"id": "dark", "label": "Dark Color", "type": "color", "default": "#1b1464"},
    {"id": "light", "label": "Light Color", "type": "color", "default": "#ffc857"},
    {"id": "amount", "label": "Amount", "type": "float", "default": 1, "min": 0, "max": 1, "step": 0.01, "percent": true}
  ],
  "sksl": "uniform shader image;\nuniform float2 size;\nuniform float time;\nlayout(color) uniform half4 dark;\nlayout(color) uniform half4 light;\nuniform float amount;\n\nhalf4 main(float2 coord) {\n    half4 c = image.eval(coord);\n    if (c.a <= 0.0001) return half4(0);\n    float3 rgb = float3(c.rgb / c.a);\n    float l = dot(rgb, float3(0.2126, 0.7152, 0.0722));\n    float3 tone = mix(float3(dark.rgb), float3(light.rgb), l);\n    return half4(half3(mix(rgb, tone, amount)) * c.a, c.a);\n}\n"
}
```

To try it, open **Effects > Added > + Add effect** in AbsentMotion and pick the file.

### Fields

| Field | Needed | What it is |
| --- | --- | --- |
| `id` | yes | 1 to 40 lowercase letters, digits or dashes. Different for each effect in a pack. Keep it the same when you update the effect. |
| `name` | yes | The name shown in the Effects Library, up to 80 characters. |
| `category` | yes | Where the effect also appears: `color`, `blur`, `distort`, `stylize`, `noise`, `repeat`, `key`, `move`, `beat`, `3d`, `text` or `other`. Anything else becomes `other`. |
| `params` | yes | The settings, up to 32 (see below). Use `[]` for none. |
| `sksl` | yes | The shader, up to 64 KB. Lines are separated by `\n` inside the JSON string. |
| `description` | no | One or two sentences about what the effect does. |
| `author` | no | Your name, shown when people add the effect. |
| `licence` | no | The licence people can use the effect under, for example `CC BY 4.0`. |
| `version` | no | A whole number. Raise it when you share an update. |

### Settings

Each setting has an `id` (also the name of its shader variable), a `label` shown in the app, a `type` and a `default`.

| Type | In the app | Extra fields | Default | In the shader |
| --- | --- | --- | --- | --- |
| `float` | slider | `min`, `max`, `step`, `percent` (show as %), `unit` | number | `uniform float id;` |
| `angle` | angle dial, in degrees | `min`, `max`, `step` | number | `uniform float id;` |
| `point` | two numbers (X and Y) | `min`, `max`, `step` | `[x, y]` | `uniform float2 id;` |
| `color` | color picker | | `"#rrggbb"` or `"#aarrggbb"` | `layout(color) uniform half4 id;` |
| `switch` | on or off | | `true` or `false` | `uniform float id;` (1 or 0) |
| `choice` | list | `options`: list of names | index of the first chosen option | `uniform float id;` (0, 1, 2 ...) |

Every setting can be animated with keyframes like the built-in effects.

### The shader

The app gives every shader these, so declare the ones you use:

```
uniform shader image;   // the layer you put the effect on
uniform float2 size;    // the layer's size in pixels
uniform float time;     // the layer's time in seconds
```

Then write `half4 main(float2 coord)`. It gets a pixel position on the layer (in pixels, 0,0 is the top left) and returns that pixel's color. Read the layer with `image.eval(coord)`. You can read other positions too, which is how blurs and distortions work.

Colors have premultiplied alpha. Divide by alpha before changing colors and multiply back at the end, like the example does. Return `half4(0)` for see-through pixels.

Keep it fast: the shader runs for every pixel of every frame. Avoid long loops.

### Packs

To share several effects at once, put their `.json` files in a ZIP file (at the top level, not in a folder) and rename it from `.zip` to `.amfx`. A pack can hold up to 20 effects and must be 512 KB or smaller.

## Sharing your effect

1. Test it in AbsentMotion first. If the app says **Doesn't work on this device**, the shader has a mistake.
2. Upload the `.json` or `.amfx` file to any file hosting website (an anonymous one, Google Drive or MEGA). Anyone with the link must be able to download it.
3. Send the link with the [Community form](https://forms.gle/Xyn4TiKNJ9kUPQ7x8) and choose **Effect**.

A person checks every effect before it goes up.

## Rules for effects

- You wrote the shader, or its licence lets you share it and you say where it came from in the description.
- No effects taken or converted from another app's files.
- One effect file is 512 KB or smaller, and a pack holds up to 20 effects.
- Effects are shared under CC BY 4.0 per [LICENSE-ITEMS.md](../LICENSE-ITEMS.md), unless the effect's `licence` field says otherwise.
- If something you made was shared here and you want it taken down, contact **comett1225** on Discord.
