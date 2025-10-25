# Vendor Libraries

This directory contains third-party JavaScript libraries used by the LG R290 Heat Pump Control System.

## Moral and Practical Considerations

### The Dilemma

There was careful consideration about whether to commit these vendor libraries to the repository or rely on external CDNs. This README documents both the concerns and the rationale behind the decision.

### Concerns About Committing Vendor Libraries

1. **Repository Bloat** - Adding ~623KB of third-party code increases repository size
2. **Duplication** - These libraries are publicly available on CDNs and npm
3. **Maintenance Burden** - We become responsible for tracking security updates
4. **Licensing Responsibility** - Must ensure proper attribution and license compliance
5. **Version Management** - Risk of outdated libraries if not actively maintained

### Rationale For Local Vendoring

After consideration, the decision was made to **commit the libraries locally** for the following reasons:

1. **System Criticality** - This controls a home heating system that should function reliably 24/7, regardless of external infrastructure
2. **Offline Operation** - The system must work even without internet connectivity or during CDN outages
3. **Production Reliability** - External dependencies (jsdelivr.net, cdnjs.com) introduce single points of failure
4. **Reproducibility** - Exact versions are frozen, preventing unexpected breaking changes
5. **Self-Contained Deployment** - Docker containers should be fully independent
6. **License Compliance** - Both libraries use MIT license, which explicitly permits redistribution
7. **Reasonable Size** - 623KB is negligible for modern systems (2025)
8. **Best Practice** - Common for production systems requiring high availability

### Conclusion

For a **critical home automation system** controlling heating infrastructure, **reliability trumps repository aesthetics**. The heating system should not fail because an external CDN is unreachable.

---

## Included Libraries

### Three.js r134
- **File**: `three.min.js`
- **Size**: 602 KB (minified)
- **Version**: r134
- **License**: MIT
- **Source**: https://cdnjs.cloudflare.com/ajax/libs/three.js/r134/three.min.js
- **Homepage**: https://threejs.org/
- **Purpose**: 3D graphics library required by Vanta.js for WebGL rendering

### Vanta.js HALO Effect
- **File**: `vanta.halo.min.js`
- **Size**: 21 KB (minified)
- **Version**: 0.5.24
- **License**: MIT
- **Source**: https://cdn.jsdelivr.net/npm/vanta@0.5.24/dist/vanta.halo.min.js
- **Homepage**: https://www.vantajs.com/
- **Purpose**: Animated HALO background effect for screensaver

---

## License Information

Both libraries are distributed under the **MIT License**, which permits:
- Commercial use
- Modification
- Distribution
- Private use

### Three.js License
```
The MIT License

Copyright © 2010-2024 three.js authors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.
```

### Vanta.js License
```
The MIT License

Copyright (c) 2018 Teng Bao

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.
```

---

## Updating Libraries

If security updates or new features are needed, update the libraries as follows:

### Update Three.js
```bash
cd ui/static/vendor/
curl -o three.min.js https://cdnjs.cloudflare.com/ajax/libs/three.js/r[VERSION]/three.min.js
```

### Update Vanta.js
```bash
cd ui/static/vendor/
curl -o vanta.halo.min.js https://cdn.jsdelivr.net/npm/vanta@[VERSION]/dist/vanta.halo.min.js
```

**Note**: After updating, test the screensaver thoroughly to ensure compatibility.

---

## Verification

To verify library integrity, check file sizes and versions:

```bash
ls -lh ui/static/vendor/
# Expected:
# three.min.js      ~602 KB
# vanta.halo.min.js ~21 KB
```

---

**Last Updated**: 2025-10-25
**Downloaded By**: Claude Code (via user request)
**Reason**: Eliminate external CDN dependencies for production reliability
