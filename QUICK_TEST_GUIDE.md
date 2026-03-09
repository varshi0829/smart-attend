# Quick Test Guide - QR Scanner Enhancements

## Test 1: Higher Resolution (1 minute)

1. Open student portal on mobile device
2. Open browser DevTools (Chrome: `chrome://inspect`)
3. Go to QR scanner step
4. Check console for camera resolution:
   ```
   Look for: "1280x720" or "1920x1080" in video track settings
   ```
5. ✅ **Pass:** Resolution is 1280x720 or higher
6. ❌ **Fail:** Resolution is 640x480 or lower

---

## Test 2: Auto-Zoom (2 minutes)

### Setup
1. Display instructor QR on a screen
2. Stand 2-3 meters away (QR should be out of focus)
3. Open student portal and go to scanner

### Test Steps
1. Point camera at distant QR
2. Wait 2 seconds (scanner will fail to decode)
3. **Check console:** Should see `(zoom: 1.5x)`
4. Wait 2 more seconds
5. **Check console:** Should see `(zoom: 2.0x)`
6. Move closer or wait for zoom to reach 3.0x
7. QR should decode successfully
8. **Check console:** Should see `Applied zoom: 1.0x` (reset)

### Expected Console Output
```
[QR] decode miss x1: No QR in frame yet (zoom: 1.0x)
[QR] decode miss x2: No QR in frame yet (zoom: 1.0x)
[ZOOM] Applied zoom: 1.5x
[QR] decode miss x3: No QR in frame yet (zoom: 1.5x)
[QR] decode miss x4: No QR in frame yet (zoom: 1.5x)
[ZOOM] Applied zoom: 2.0x
[QR] onScanSuccess fired. raw= SA_...
[ZOOM] Applied zoom: 1.0x
```

---

## Test 3: Zoom Reset (30 seconds)

1. Scan a QR successfully (zoom should be at 1.0x)
2. Go back to scanner step
3. **Check:** Zoom should start at 1.0x (not previous zoom level)
4. ✅ **Pass:** Zoom resets on scanner restart

---

## Test 4: No Zoom Support (iOS Safari)

1. Open student portal on iPhone (Safari)
2. Go to scanner step
3. **Check console:** Should see `Camera does not support zoom`
4. Scanner should still work normally
5. ✅ **Pass:** No errors, scanner functional

---

## Quick Visual Test (30 seconds)

1. Display QR on laptop screen
2. Stand 2 meters away with phone
3. Point camera at QR
4. **Watch:** QR should gradually come into focus as zoom increases
5. **Result:** QR scans successfully within 10 seconds

---

## Troubleshooting

### Zoom Not Working
- Check browser: Chrome/Samsung Internet work best
- Check device: Some cameras don't support digital zoom
- Check console: Look for `Camera does not support zoom`

### Resolution Not 1280x720
- Device may not support high resolution
- Browser will use closest available resolution
- Check `track.getSettings()` in console for actual resolution

### Scanner Slower Than Before
- Higher resolution = slightly slower decode
- Expected: 1-2 extra frames per decode
- If >5 frames slower, check device performance

---

## Success Criteria

✅ Resolution is 1280x720 or higher  
✅ Zoom increases every 2 scan failures  
✅ Zoom maxes out at 3.0x  
✅ Zoom resets to 1.0x on successful scan  
✅ Zoom resets to 1.0x on scanner restart  
✅ No errors on devices without zoom support  
✅ QR scans successfully from 2+ meters away

---

**Estimated Test Time:** 5 minutes total
