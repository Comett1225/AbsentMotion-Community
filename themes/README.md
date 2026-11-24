# Themes

Themes people made for [AbsentMotion](https://github.com/Comett1225/AbsentMotion). A theme changes the colors of the whole app: the editor, the timeline, the home screen and the menus.

## Using a theme

- In AbsentMotion 5.3.1 or later, open **Home > Community > Themes**, tap a theme, and tap **Add**.
- Or download a theme file (it ends in `.json`), then open **Settings > Import theme file...** and pick it.

The theme is applied at once. AbsentMotion keeps one custom theme at a time, so importing a new file replaces the last one. The built-in looks (Light, Dark and Daylight) are always there to go back to.

If you set **Theme color** in Settings to anything but **Default**, it replaces the theme's accent colors (`Accent`, `AccentLit`, `AccentGlow`, `AccentDeep`, `OnAccent`, `HomeAccent` and `OnNavyAccent`). Set it back to **Default** to see the accent the theme sets.

## Making your own theme

A theme is a small text file. It lists the colors you want to change.

### Example

Save this as `mint.json`:

```json
{
  "name": "Mint",
  "Accent": "#5BD6A4",
  "HomeAccent": "#1B7A4A"
}
```

Import it and the app looks the same as before, except that the accent is mint green.

### Rules

- The file is plain text in JSON format, saved with the `.json` ending, in UTF-8.
- It can be at most **64 KB**. A bigger file is refused.
- `name` is optional. It is cut to 40 characters.
- Every other line is a color name from the table below, then a colon, then the color in quotes. Names are written exactly as in the table, with capital letters. Put a comma after every line except the last.
- Colors are written as `"#RRGGBB"` (red, green, blue) or `"#AARRGGBB"` (alpha first, then red, green, blue). Letters can be small or capital. The short form `#RGB` is not accepted.
- **Alpha** is how solid a color is. `FF` is fully solid, `80` is half see-through and `00` is invisible. `"#RRGGBB"` is the same as `"#FFRRGGBB"`. Most colors should be solid. Alpha is meant for the veil and press colors: `Scrim`, `MenuScrim`, `PressEditor` and `PressHome`.
- Colors you leave out keep the AbsentMotion look. The one exception: if you set `Gold` and leave out `Favorite`, the favorite star takes the `Gold` color.
- A name that is not in the table is ignored.
- The file needs at least one color. If a color is written in the wrong way, the app refuses the file and names the color.

### Tips

- Start from an existing theme and change a few colors. The full example at the end of this page is a good starting point. Copy it, give it a new `name`, and change what you like.
- The editor and the home screen are separate. The editor colors are dark in the AbsentMotion look. The home screen colors (the Home screen group) are light. You can make either one light or dark.
- Keep text readable. Text colors (`OnDark`, `HomeInk` and friends) need to stand out against the colors behind them. A pair like `Accent` and `OnAccent` should always differ a lot.
- Change a few colors, import, look, and repeat. The whole file is read again at each import.

## Every color

The colors are in groups. The "Where it shows" column says the main places. Some colors show in more places than listed.

### Editor

| Name | Where it shows |
|---|---|
| `TopBar` | The editor's main background: the top bar, and the page behind the panels. Also the full-screen tool screens, such as presets. |
| `PreviewBg` | The area behind the video preview, the inside of the panels' dark boxes (sliders, pickers), and the empty space after the end of the timeline. |
| `TimelineBg` | The timeline background, the play bar under the preview, and the row behind the layer tabs. |
| `Panel` | Bottom sheets and tool panels (voice, captions, stretch), the media library on a computer, and the level meters. |
| `PanelInset` | Boxes sitting on a panel: tiles in the element library, the font browser, the number keys' resting color, unselected options. |
| `Button` | Buttons and tiles in the editor, effect rows, and the line between the timeline's layer names and the bars. |
| `Field` | Dialogs in the editor, text fields, list rows and menu backgrounds. |
| `FieldHi` | Selected or raised items: the chosen tab in a switch, sliders' empty track, the edge of the project safety dialogs, and some buttons on the home screen of a computer. |
| `Chosen` | The graph background in the Easing panel, the picked item in Border and Shadow, and the dark end of the gradient preview. |
| `Well` | Dark wells: tiles in the Media and Audio tabs, slider tracks (Blending, switches), and the Done key on the number keypad. |
| `Deepest` | The darkest areas: the underline on the top bar, the color picker grid, the level meter background and the text editor's top strip. |
| `Line` | Thin dividing lines: timeline ticks and header edge, list lines in menus, borders of the tutorial card and the font browser. |
| `MenuLine` | Divider lines inside the editor menus and the Easing panel's menu. |
| `PressEditor` | The press and hover highlight on the computer editor. |

### Timeline

These are the layer bars and marks in the timeline.

| Name | Where it shows |
|---|---|
| `LayerBar` | The bar of a normal layer on the timeline (video, picture, shape and so on). |
| `LayerBarStripe` | The stripes drawn on top of a layer bar. |
| `TextBar` | The bar of a text layer on the timeline. |
| `TextBarStripe` | The stripes drawn on a text layer bar. |
| `AudioBar` | The bar of a sound layer on the timeline. |
| `AudioWave` | The sound wave drawn inside a sound bar. |
| `OnBar` | The layer name written on layer and text bars. |
| `OnAudioBar` | The layer name written on a sound bar. |
| `Bookmark` | The bookmark markers on the timeline. |
| `Gold` | Retime marks on the timeline, the unselected points in the preview, the search text and the progress ring in the font browser, the fine-adjust line in sliders, and the numbers on the keypad that are outside the range. |

### Keypad and menus

The number keypad in the layer tools, and the dark boxes behind previews.

| Name | Where it shows |
|---|---|
| `KeyDigit` | The number keys (0 to 9) of the number keypad in the layer tools. |
| `KeySymbol` | The sign, point and backspace keys of the same keypad. |
| `Cool` | The blue label on a keypad key, and the outline of the incoming side in the motion sheets. |
| `CoolDeep` | The background behind the selected number on a keypad key. |
| `Scrim` | The dark boxes behind previews: tool previews on the home screen (range, compress, tool kit), export preview and the finished export screen, and Community thumbnails that have no picture. |
| `OnScrim` | Text and icons on top of the Scrim: export preview buttons, the page count, the play button, and the placeholder icon on Community items. |

### Accent

| Name | Where it shows |
|---|---|
| `Accent` | The main color. Selected items, active sliders, the Export button on the editor top bar, the snap line and selection on the timeline, the play marker and the main buttons. Used in the most places of all. |
| `AccentLit` | A brighter accent: volume and blending sliders, the thumb of the editor's switches, the folder icon on the computer editor. |
| `AccentGlow` | A light accent used for highlights inside panels, such as the border and label of the active keypad key. |
| `AccentDeep` | A dark accent: the track of an editor switch when it is on, the preview's handles, and the ring of a chosen color. |
| `OnAccent` | Text and icons on top of the accent: the Export icon, accent buttons, chosen chips. |
| `Warning` | Warnings and errors: outdated preview, missing files, limits that the clip does not fit, and the delete or danger button in the project safety dialogs. |
| `Favorite` | The filled star of favorites in the text editor and the effect browser. |

### Text on dark

Text and icons in the editor.

| Name | Where it shows |
|---|---|
| `OnDark` | The main text and icons in the editor. The most used color of all. |
| `OnDarkDim` | Softer text and icons: counts, hints, empty-list messages, small icons on the computer editor. |
| `Caption` | Small help text and arrows in panels, and the guide lines in the point editor. |
| `Faint` | Quiet icons and lines: unselected icons in the point editor, Blending and Border and Shadow icons, tick marks, the color picker's idle state. |
| `Inactive` | Switched-off or idle things: the timeline ruler ticks and grips, switch tracks that are off, and the Link and Camera boxes in the move panels. |

### Home screen

The home screen, the settings drawer, the New project sheet, the Export screen and the onboarding screens.

| Name | Where it shows |
|---|---|
| `HomeBg` | The home screen background, and the soft boxes on the home screen, such as the What's new header and text fields in dialogs. |
| `Card` | Cards and rows on the home screen: Tools, Templates, the settings drawer's rows, menus, the Export screen top bar and the tutorial card. |
| `SheetBg` | The background of sheets: the New project sheet, the Export screen, the onboarding screens and the About screen. |
| `HomeDrawer` | The settings drawer's background. |
| `HomePanel` | Quiet panels on the home screen: the settings drawer's grouped rows, Community items without a picture, and the safety dialogs' buttons. |
| `Navy` | The home screen's main dark color. Headings, icons, chosen tabs and chips, selected buttons and checkboxes, and the progress bar. Despite the name it can be any color. |
| `OnNavy` | Text and icons on top of Navy, for example on a chosen tab or button. |
| `OnNavyAccent` | Accent text and icons on Navy: the labels of chosen options, the Export button label, and the progress heat text on the Export screen when the home screen is light. |
| `NavyHi` | The chosen row in the settings drawer's lists. |
| `NavyLine` | Lines and borders in the settings drawer's lists, the New project sheet's lists and the Templates tab's chips. |
| `HomeAccent` | The accent of the home screen: switches that are on, radio buttons, check marks in menus, alert text on the Export screen, and the danger button in the home safety dialogs. |
| `HomeInk` | The main text on the home screen. |
| `HomeMid` | Second-level text and icons on the home screen: version line, arrows, handles and labels. |
| `HomeDim` | Third-level text on the home screen: help lines, tool descriptions and small chevrons. |
| `HomeFaint` | The faintest home elements: the unselected page dots and the link icon in the New project sheet. |
| `HomeLine` | Thin lines and borders on the home screen, the track of progress bars, and the chosen range button in tools. |
| `MenuScrim` | The veil that covers the home screen when a menu is open. |
| `PressHome` | The press and hover highlight on the home screen. |

### Switches and others

| Name | Where it shows |
|---|---|
| `SwitchOff` | The track of a switch that is off: the settings drawer and the Export screen. |
| `Thumb` | The round thumb of a switch that is off, on the Export screen and on the editor's switches, and the marker on its sliders. |

## Sharing a theme

1. Upload your `.json` file to a file hosting site and copy the link.
2. Send the link with the [Community form](https://forms.gle/Xyn4TiKNJ9kUPQ7x8). Choose **Theme**.

Rules:

- The file is at most 64 KB.
- It has a `name`.
- It is your own work.
- The theme name does not contain another app's name or logo.

## Full example: Light Green

This theme changes most colors. The editor is deep blue-purple with a bright green accent, and the home screen is light with the same green. Save it as `light-green.json`.

```json
{
 "name": "Light Green",
 "TopBar": "#202332",
 "PreviewBg": "#141620",
 "TimelineBg": "#191B27",
 "Panel": "#333750",
 "PanelInset": "#292D40",
 "Button": "#292D40",
 "Field": "#141620",
 "FieldHi": "#3B3F54",
 "Chosen": "#141620",
 "Well": "#191B27",
 "Deepest": "#0C0D13",
 "Line": "#222535",
 "MenuLine": "#222535",
 "KeyDigit": "#626575",
 "KeySymbol": "#252944",
 "Scrim": "#F2050508",
 "PressEditor": "#1CFFFFFF",
 "OnDark": "#FFFFFF",
 "OnDarkDim": "#A9ABB4",
 "Caption": "#B8B9C2",
 "Faint": "#767A88",
 "Inactive": "#626575",
 "OnScrim": "#FFFFFF",
 "Accent": "#00FFA8",
 "AccentLit": "#69FC97",
 "AccentGlow": "#9CFFD6",
 "AccentDeep": "#316463",
 "OnAccent": "#000000",
 "Gold": "#FFCD4B",
 "Favorite": "#FFCD4B",
 "HomeBg": "#F6F6F6",
 "Card": "#FFFFFF",
 "SheetBg": "#EAEAEC",
 "Navy": "#1E2239",
 "HomeAccent": "#00FFA8",
 "OnNavy": "#FFFFFF",
 "OnNavyAccent": "#00FFA8",
 "NavyHi": "#333750",
 "NavyLine": "#43486B",
 "HomeInk": "#000000",
 "HomeMid": "#494C5A",
 "HomeDim": "#5D606F",
 "HomeFaint": "#BBBBBB",
 "HomeLine": "#D9D9DD",
 "HomePanel": "#EAEAEC",
 "HomeDrawer": "#FFFFFF",
 "SwitchOff": "#A3A3A5",
 "Thumb": "#ECECEC",
 "MenuScrim": "#B30F1010",
 "PressHome": "#12000000"
}
```
