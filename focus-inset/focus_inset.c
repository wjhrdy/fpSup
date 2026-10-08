/* fp 5.02 experimental resident adapters: see README.md.
 * No preference setter or saved settings structure is changed. */
#include <stdint.h>
#include <stddef.h>

#define INLINE static inline __attribute__((always_inline))
#define X 96u
#define Y 72u
#define WIDTH 224u
#define HEIGHT 148u
#define WORDS 39u

INLINE uint32_t read32(uint32_t address) {
    return *(const volatile uint32_t *)(uintptr_t)address;
}
INLINE uint32_t call0(uint32_t address) {
    return ((uint32_t (*)(void))(uintptr_t)address)();
}
INLINE int manual_still(void) {
    /* Existing focus-lift/flicker STILL gate; native lens AF capability. */
    return read32(0xc3202cf0u) == 0 && call0(0xc03626c0u) == 0;
}

INLINE int valid_crop(const uint32_t *p) {
    return p[0] == 1024 && p[1] == 682 &&
        ((p[4] == 256 && p[5] == 171) || (p[4] == 128 && p[5] == 85)) &&
        p[2] <= p[0] - p[4] && p[3] <= p[1] - p[5];
}

/* OpNew's first open prepares PIP before its state becomes 5. Its native
 * crop submission otherwise skips the Result crop and leaves the processing
 * cache empty. Supply that existing path a local view of the ready PIP;
 * never change the real controller state or Result settings. */
int focus_inset_initial_crop(uint32_t *dst, const uint32_t *src) {
    for (unsigned i = 0; i < 8; ++i) dst[i] = src[i];
    uint32_t params = read32(0xc375d844u);
    if (src[3] != 0 || (src[6] != 1 && src[6] != 2) || !params ||
        read32(params) > 1 || read32(params + 0x28u) != 2 ||
        !valid_crop((const uint32_t *)(uintptr_t)(params + 0x2cu)) ||
        read32(0xc3033a88u) != 2 || !manual_still()) return 0;
    dst[3] = 5;
    return 1;
}

/* C0305B98 normally restricts peaking to the centred PIP rectangle. The
 * inset is already baked into the main preview, so process its whole native
 * visible rectangle. This local output has inclusive right/bottom endpoints;
 * no peaking preference or shared Result/Common field is changed. */
int focus_inset_peaking(uint32_t *out, const uint32_t *event) {
    uint32_t params = read32(0xc375d844u);
    if (!params || read32(params) > 1 || read32(params + 0x28u) != 2 ||
        (read32(0xc3075174u) != 0 && read32(0xc3075174u) != 2) ||
        !manual_still()) return 0;
    const uint32_t *rect = (const uint32_t *)(uintptr_t)event[1];
    if (!rect || !((rect[0] == 1920 && rect[1] == 1080) ||
                   (rect[0] == 1024 && rect[1] == 682)) ||
        !rect[4] || !rect[5] || rect[4] > rect[0] || rect[5] > rect[1] ||
        rect[2] > rect[0]-rect[4] || rect[3] > rect[1]-rect[5]) return 0;
    out[0] = rect[2]; out[1] = rect[3];
    out[2] = rect[2] + rect[4] - 1;
    out[3] = rect[3] + rect[5] - 1;
    return 1;
}

/* Postprocess only the live-preview mode descriptor at C04369F8. The MF
 * controller and Common's kind/active fields remain stock. In particular,
 * mode 2 (capture), explicit fullscreen and custom sensor overrides pass
 * through. Native selection chooses its existing MAG4/MAG8 PINP profile. */
int focus_inset_preview(uint32_t mode, uint32_t *out,
                       const uint32_t *common, uint32_t override) {
    if (mode > 1 || override || common[0x58c/4] || !manual_still()) return 0;
    const uint32_t *crop = common + 0x59c/4;
    out[8] = 2;
    if (valid_crop(crop)) {
        for (unsigned i = 0; i < 6; ++i) out[9+i] = crop[i];
    } else {
        /* Stock centred 4x crop, before the first interactive selection. */
        out[9] = 1024; out[10] = 682; out[11] = 384;
        out[12] = 256; out[13] = 256; out[14] = 171;
    }
    return 1;
}

/* C0436AF0 derives the native sensor crop for the selected preview. Use the
 * validated local mode crop, rather than the inactive global Common crop.
 * The native routine and its supported crop calculation still run normally. */
const uint32_t *focus_inset_crop(const uint32_t *stock) {
    uint32_t params = read32(0xc375d844u);
    if (!params || read32(params) > 1 || read32(params + 0x28u) != 2 ||
        read32(0xc3075174u) || !manual_still()) return stock;
    const uint32_t *crop = (const uint32_t *)(uintptr_t)(params + 0x2cu);
    return valid_crop(crop) ? crop : stock;
}

/* The stock exit's repaint happens inside the old-state callback, before
 * the new state's GUI controls finish updating. An unchanged PIP pipeline
 * no longer supplies the later repaint. Request one after both callbacks
 * and their locks finish, only for entering/leaving MF adjustment. */
int focus_inset_refresh(uint32_t manager, uint32_t previous) {
    uint32_t state = read32(manager + 4u);
    if (!state) return 0;
    uint32_t current = read32(state);
    if (current == previous ||
        !((previous == 1 && (current == 4 || current == 5)) ||
          ((previous == 4 || previous == 5) && current == 1)) ||
        !manual_still()) return 0;
    uint32_t draw = call0(0xc05278f8u);
    typedef void (*redraw_fn)(uint32_t, const uint32_t *);
    /* Exact stock ReqForceDraw {0101,FFFFFFFF,0}: no retained callback. */
    ((redraw_fn)0xc0527e68u)(draw, (const uint32_t *)0xc0cd71e8u);
    return 1;
}

/* OpNew output channel 4 is the PIP image, baked into the full preview.
 * C01D69D0 copies this descriptor into its volatile output cache. Its native
 * consumers C01CB9B8 use width/height, horizontal padding and top offset.
 * Leave the original stack descriptor and every saved preference untouched. */
int focus_inset_picture(uint32_t *dst, uint32_t instance, uint32_t channel,
                        const uint32_t *src) {
    for (unsigned i = 0; i < 14; ++i) dst[i] = src[i];
    if (instance || channel != 4 || !manual_still() ||
        src[0] != 808 || src[1] != 538 || src[2] != 406 ||
        src[3] != 406 || src[4] != 271 || src[5] ||
        src[6] || src[7] != 4 || src[11] != 2 || src[12] != 1) return 0;
    /* Native preview is 1620x1080, GUI is 1024x682. Keep its 1620-pixel
     * stride and even chroma alignment; bottom padding is unused natively. */
    dst[0] = 354; dst[1] = 234;
    dst[2] = 152; dst[3] = 1114; dst[4] = 114;
    return 1;
}

/* Pure descriptor preparation. A verified native adapter must supply fresh
 * STILL/focus/PIP/physical-output facts, then submit this local copy. */
int focus_inset_prepare(uint16_t *dst, const uint16_t *src,
                        uint32_t still, uint32_t focus_mode,
                        uint32_t zoom_kind, uint32_t output) {
    uintptr_t a = (uintptr_t)dst, b = (uintptr_t)src;
    if (!dst || !src || (a & 3u) || (b & 3u) ||
        (a <= b ? b-a : a-b) < WORDS*4u)
        return -1;
    for (unsigned i = 0; i < WORDS * 2; ++i) dst[i] = src[i];
    if (still != 1 || focus_mode != 2 || zoom_kind != 2 || output != 1 ||
        ((const uint32_t *)src)[0] != 0 ||
        src[0x60 / 2] != 1024 || src[0x62 / 2] != 682 ||
        src[0x64 / 2] != 1024 || src[0x66 / 2] != 682 ||
        src[0x68 / 2] || src[0x6a / 2] ||
        ((const uint32_t *)src)[0x88 / 4] ||
        ((const uint32_t *)src)[0x98 / 4]) return 0;
    uint32_t sw = src[0x78 / 2], sh = src[0x7a / 2];
    uint32_t w = src[0x7c / 2], h = src[0x7e / 2];
    uint32_t sx = src[0x80 / 2], sy = src[0x82 / 2];
    if (!w || !h || sx + w > sw || sy + h > sh ||
        (w | h | sx | sy) & 1u) return 0;
    /* Preserve source centre and the existing pixel magnification. */
    uint32_t cw = (w * WIDTH / 1024u) & ~1u;
    uint32_t ch = (h * HEIGHT / 682u) & ~1u;
    if (cw < 8 || ch < 8) return 0;
    dst[0x64 / 2] = WIDTH; dst[0x66 / 2] = HEIGHT;
    dst[0x68 / 2] = X; dst[0x6a / 2] = Y;
    dst[0x7c / 2] = cw; dst[0x7e / 2] = ch;
    dst[0x80 / 2] = (sx + (w - cw) / 2u) & ~1u;
    dst[0x82 / 2] = (sy + (h - ch) / 2u) & ~1u;
    return 1;
}

INLINE int still_page(const char *p) {
    if (!p || p[0]!='L' || p[1]!='V' || p[2]!='_' || p[3]!='S' ||
        p[4]!='T' || p[5]!='I' || p[6]!='L' || p[7]!='L' || p[8]!='_') return 0;
    return (p[9]=='L' && p[10]=='A' && p[11]=='R' && p[12]=='G' && p[13]=='E' && !p[14]) ||
           (p[9]=='M' && p[10]=='E' && p[11]=='D' && p[12]=='I' && p[13]=='U' && p[14]=='M' && !p[15]);
}

/* The stock Magnify parent is hidden after leaving MF adjustment. Override
 * effective visibility only for its border leaf, never that parent or its
 * controls. No scene visibility property, animation or setting is changed. */
uint32_t focus_inset_visible(uint32_t object, uint32_t stock) {
    if (stock || !object || (object & 3u) ||
        read32(object + 0x18u) != 9094 || read32(object + 0x14u) ||
        !read32(object + 0x30u)) return stock;
    uint32_t p = read32(object + 0x1cu);
    if (!p || read32(p + 0x18u) != 9093) return stock;
    p = read32(p + 0x1cu);
    if (!p || read32(p + 0x18u) != 9085) return stock;
    p = read32(p + 0x1cu);
    if (!p || read32(p + 0x18u) != 7894) return stock;
    p = read32(p + 0x1cu);
    if (!p || read32(p + 0x18u) != 7780) return stock;
    p = read32(p + 0x1cu);
    if (!p || !read32(p + 0x30u)) return stock;
    uint32_t magnify = read32(p + 0x18u);
    uint32_t root = read32(p + 0x1cu);
    if (!root || read32(root + 0x18u) != 1 || read32(root + 0x1cu) ||
        !read32(root + 0x30u)) return stock;
    uint32_t screen = read32(root + 0x80u);
    if (!screen || read32(screen + 0xcu) != root) return stock;
    const char *name = (const char *)(uintptr_t)read32(screen + 8u);
    if (!still_page(name) || magnify != (name[9]=='L' ? 9092u : 8938u)) return stock;
    uint32_t params = read32(0xc375d844u);
    if (!params || read32(params) > 1 || read32(params + 0x28u) != 2 ||
        read32(0xc3075174u) || !manual_still()) return stock;
    return 1;
}

INLINE uint32_t child(uint32_t parent, uint32_t id) {
    uint32_t count = read32(parent + 0x54u);
    uint32_t table = read32(parent + 0x60u), found = 0;
    if (count > 16 || !table || (table & 3u)) return 0;
    for (uint32_t i = 0; i < count; ++i) {
        uint32_t p = read32(table + i * 4u);
        if (!p || (p & 3u) || read32(p + 0x1cu) != parent) return 0;
        if (read32(p + 0x18u) == id) {
            if (found) return 0;
            found = p;
        }
    }
    return found;
}
INLINE uint32_t component(uint32_t object, uint32_t index,
                          uint32_t plugin, uint32_t properties) {
    if (read32(object + 0x40u) <= index) return 0;
    uint32_t p = read32(read32(object + 0x4cu) + index * 4u);
    if (!p || (p & 3u) || read32(p + 0x18u) != plugin ||
        read32(p + 0x14u) != properties) return 0;
    return p;
}

/* Variable dispatch C05DC178 finishes the native binding updates and locks on
 * the UI thread. The unchanging PIP pipeline leaves Magnify one event behind.
 * MagnifyStatus owns three complementary visibility clips: Magnify and the
 * two normal shooting groups. Correct their current heap booleans together
 * through native dirty callbacks; defaults and saved settings stay stock. */
int focus_inset_controls(uint32_t screen) {
    if (!screen || (screen & 3u)) return 0;
    const char *name = (const char *)(uintptr_t)read32(screen + 8u);
    if (!still_page(name)) return 0;
    uint32_t root = read32(screen + 0xcu);
    if (!root || (root & 3u) || read32(root + 0x18u) != 1 ||
        read32(root + 0x1cu) || read32(root + 0x80u) != screen) return 0;
    uint32_t parent = child(root, name[9]=='L' ? 9092u : 8938u);
    if (!parent || read32(parent + 0x14u)) return 0;
    uint32_t objects[3] = {parent,
        child(root, name[9]=='L' ? 8938u : 8936u),
        child(root, name[9]=='L' ? 9113u : 8937u)};
    uint32_t bases[3];
    typedef uint32_t (*kind_fn)(uint32_t);
    for (unsigned i = 0; i < 3; ++i) {
        if (!objects[i] || read32(objects[i] + 0x14u)) return 0;
        bases[i] = component(objects[i], 0, 0xc2dff5f4u, 13);
        if (!bases[i] || read32(bases[i] + 0x24u) != objects[i] ||
            ((kind_fn)0xc05d6fc1u)(bases[i]) != 2) return 0;
    }
    uint32_t params = read32(0xc375d844u), kind = read32(0xc3075174u);
    if (!params || read32(params) > 1 || read32(params + 0x28u) != 2 ||
        (kind != 0 && kind != 2) || !manual_still()) return 0;
    uint32_t active = kind == 2 && read32(0xc3075178u) != 0;
    uint32_t changed = 0;
    typedef uint32_t (*get_fn)(uint32_t, uint32_t, uint32_t *);
    typedef uint32_t (*set_fn)(uint32_t, uint32_t, uint32_t);
    for (unsigned i = 0; i < 3; ++i) {
        uint32_t current, want = i ? !active : active;
        if (((get_fn)0xc05d6401u)(bases[i], 6, &current)) return -1;
        if (current == want) continue;
        if (((set_fn)0xc05d63a9u)(bases[i], 6, want)) return -1;
        changed = 1;
    }
    if (!changed) return 0;
    /* State-transition redraw precedes these queued UI notifications. Publish
     * the corrected controls after the binding updates have actually finished. */
    typedef void (*redraw_fn)(uint32_t, const uint32_t *);
    ((redraw_fn)0xc0527e68u)(call0(0xc05278f8u), (const uint32_t *)0xc0cd71e8u);
    return 1;
}

/* The stock white focus square has an 8-pixel dark backing and a 4-pixel
 * light stroke. Keep all native size/color/selection behavior; thin the
 * three square sizes for manual STILL, restoring stock widths otherwise. */
INLINE int frame_stroke(uint32_t root, int manual) {
    uint32_t p = child(root, 8008); if (!p) return 0;
    p = child(p, 26); if (!p) return 0;
    p = child(p, 28); if (!p) return 0;
    uint32_t lines[6];
    for (unsigned i = 0; i < 3; ++i) {
        uint32_t square = child(p, 29u + i); if (!square) return 0;
        lines[i*2] = component(square, 1, 0xc2e033e0u, 11);
        lines[i*2+1] = component(square, 2, 0xc2e033e0u, 11);
        if (!lines[i*2] || !lines[i*2+1]) return 0;
    }
    uint32_t dark = manual ? 0x40000000u : 0x41000000u; /* 2 / 8 */
    uint32_t light = manual ? 0x3f800000u : 0x40800000u; /* 1 / 4 */
    typedef uint32_t (*set_fn)(uint32_t, uint32_t, const uint32_t *);
    set_fn set = (set_fn)0xc05d6811u;
    for (unsigned i = 0; i < 3; ++i)
        if (set(lines[i*2], 3, &dark) || set(lines[i*2+1], 3, &light)) return -1;
    return 1;
}

/* Must run before geometry evaluation, on the native UI thread. Handles
 * cached objects rather than editing already-consumed serialized records.
 * Renderer integration/lifetime and the submit adapter remain unverified. */
int focus_inset_layout(uint32_t root) {
    /* The generic draw entry may receive a descendant rather than the root. */
    for (unsigned depth = 0; depth < 16; ++depth) {
        if (!root || (root & 3u)) return 0;
        uint32_t parent = read32(root + 0x1cu);
        if (!parent) break;
        root = parent;
    }
    if (read32(root + 0x18u) != 1 || read32(root + 0x1cu)) return 0;
    uint32_t screen = read32(root + 0x80u);
    if (!screen || (screen & 3u) || read32(screen + 0xcu) != root) return 0;
    const char *name = (const char *)(uintptr_t)read32(screen + 8u);
    if (!still_page(name)) return 0;
    int manual = manual_still();
    if (frame_stroke(root, manual) < 0) return -1;
    uint32_t p = root;
    p = child(p, name[9]=='L' ? 9092u : 8938u); if (!p) return 0;
    p = child(p, 7780); if (!p) return 0;
    p = child(p, 7894); if (!p) return 0;
    p = child(p, 9085); if (!p) return 0;
    p = child(p, 9093); if (!p) return 0;
    uint32_t border = child(p, 9094), mask = child(p, 9095);
    if (!border || !mask) return 0;
    uint32_t bb = component(border, 0, 0xc2dff5f4u, 13);
    uint32_t mb = component(mask, 0, 0xc2dff5f4u, 13);
    uint32_t draw = component(border, 1, 0xc2e033e0u, 11);
    uint32_t fill = component(mask, 1, 0xc2e03b9cu, 8);
    if (!bb || !mb || !draw || !fill) return 0;
    /* The preparation pass restores current properties from their scene
     * defaults. Update both RAM copies through the native initializer setter.
     * These component defaults are heap objects, not saved preferences. */
    uint32_t pos[2] = {0x42c00000u, 0x42900000u};
    uint32_t size[2] = {0x43600000u, 0x43140000u};
    uint32_t rect[4] = {0, 0, 0x43600000u, 0x43140000u};
    if (!manual) {
        pos[0] = 0x43800000u; pos[1] = 0x432b0000u;
        size[0] = rect[2] = 0x44000000u;
        size[1] = rect[3] = 0x43aa0000u;
    }
    typedef uint32_t (*vector_fn)(uint32_t, uint32_t, const uint32_t *);
    vector_fn set = (vector_fn)0xc05d6811u;
    if (set(bb, 0, pos) || set(mb, 0, pos) || set(bb, 1, size) || set(mb, 1, size) ||
        set(draw, 9, rect) || set(fill, 6, rect)) return -1;
    return 1;
}
