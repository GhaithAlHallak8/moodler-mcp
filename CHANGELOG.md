# Changelog

## [0.4.0](https://github.com/GhaithAlHallak8/moodler-mcp/compare/v0.3.0...v0.4.0) (2026-04-11)


### Features

* system browsers fallback ([#14](https://github.com/GhaithAlHallak8/moodler-mcp/issues/14)) ([2268ffa](https://github.com/GhaithAlHallak8/moodler-mcp/commit/2268ffa87ea7851bca44fcceb15d6cfb859dcf36))

## [0.3.0](https://github.com/GhaithAlHallak8/moodler-mcp/compare/v0.2.1...v0.3.0) (2026-04-11)


### Features

* **assignments:** add get_grading_table and get_grading_summary tools ([#10](https://github.com/GhaithAlHallak8/moodler-mcp/issues/10)) ([9437d5e](https://github.com/GhaithAlHallak8/moodler-mcp/commit/9437d5e157cc02b578f4551adae7e31a383171b9))
* **courses:** extract Word/PowerPoint/Excel content server-side ([#11](https://github.com/GhaithAlHallak8/moodler-mcp/issues/11)) ([b1fe5ab](https://github.com/GhaithAlHallak8/moodler-mcp/commit/b1fe5ab3b5c2613ac9cbe21fa33d38e4d2b73818))

## [0.2.1](https://github.com/GhaithAlHallak8/moodler-mcp/compare/v0.2.0...v0.2.1) (2026-04-11)


### Bug Fixes

* **ci:** build mcpb inside release-please workflow ([#7](https://github.com/GhaithAlHallak8/moodler-mcp/issues/7)) ([e4e54b1](https://github.com/GhaithAlHallak8/moodler-mcp/commit/e4e54b14dfda8e82ab5e9092f83544c60c340b53))

## [0.2.0](https://github.com/GhaithAlHallak8/moodler-mcp/compare/v0.1.0...v0.2.0) (2026-04-11)


### Features

* add mcpb manifest for bundle distribution ([76f3fc9](https://github.com/GhaithAlHallak8/moodler-mcp/commit/76f3fc9c071aa3c7c7decfab1067233ef6ee8f20))
* **cache:** add [@cached](https://github.com/cached) async decorator ([af9efb6](https://github.com/GhaithAlHallak8/moodler-mcp/commit/af9efb6d3007cdaef41bfca021b929a189c094d4))
* **cache:** add clear_cache MCP tool ([cf25c19](https://github.com/GhaithAlHallak8/moodler-mcp/commit/cf25c19480d4d545ac6e6f0b6337c57b13e8fb03))
* **cache:** add moodle_api wrappers for all cached operations ([6452f82](https://github.com/GhaithAlHallak8/moodler-mcp/commit/6452f82eecf1005866aef80dc0f62653f5fd4219))
* **cache:** add sqlite-backed TTL store ([ab44286](https://github.com/GhaithAlHallak8/moodler-mcp/commit/ab44286338ecb24c8590880909dd7334bbc94dc5))
* **config:** add CACHE_DB and CACHE_DISABLED settings ([7af1bcb](https://github.com/GhaithAlHallak8/moodler-mcp/commit/7af1bcb3cdb69d27468e42fc4679b8911b090381))
* enhance file content headers with local path information and truncation details ([deb7471](https://github.com/GhaithAlHallak8/moodler-mcp/commit/deb74716c11d4edfa1e5104ea2a853429f6857a2))
* **mcpb:** add long description, support/docs urls, and privacy policy ([e365291](https://github.com/GhaithAlHallak8/moodler-mcp/commit/e3652916a868d1c488e263313fb6e973e3ba02c8))
* **mcpb:** add rounded app icon ([ec4c9dc](https://github.com/GhaithAlHallak8/moodler-mcp/commit/ec4c9dcdf2088061173a4053517e059ae69c0ac9))
* **mcpb:** add screenshots showcasing core tool flows ([76101a1](https://github.com/GhaithAlHallak8/moodler-mcp/commit/76101a18788db35a64ce9e4b1a7fccd9449d159f))


### Bug Fixes

* **ci:** match mcpb cli output filename and include version in release asset ([65bb206](https://github.com/GhaithAlHallak8/moodler-mcp/commit/65bb206e74005ad93b7196fff3c042bcf02e2903))
* **config:** require MOODLE_URL at startup and strip trailing slash ([3b25fdc](https://github.com/GhaithAlHallak8/moodler-mcp/commit/3b25fdc7fea412781f594e4c4dbbc39c7c5359b4))
* **mcpb:** remove hardcoded moodle url default from manifest ([64e873a](https://github.com/GhaithAlHallak8/moodler-mcp/commit/64e873a4d7b415fa8039534b494ffbcf6cd2af3a))
* remove default Moodle URL prev to make it university-agnostic ([be181bd](https://github.com/GhaithAlHallak8/moodler-mcp/commit/be181bdd8cb234d09dbac0fb507823cc574c8586))
* resolve B904 exception chaining in client.py ([64e69ec](https://github.com/GhaithAlHallak8/moodler-mcp/commit/64e69ecfc79c96f0c97049bcc366e943f8ef76b8))


### Documentation

* add banner image to readme header ([16a3a81](https://github.com/GhaithAlHallak8/moodler-mcp/commit/16a3a816da84425288b43eca0bac2088be670ab3))
* add CONTRIBUTING guide ([31622bb](https://github.com/GhaithAlHallak8/moodler-mcp/commit/31622bb6f18a12b10c3355404f6ea97961861d1c))
* rewrite readme to match actual auth model and tool list ([8351c8f](https://github.com/GhaithAlHallak8/moodler-mcp/commit/8351c8fca30caf17519b591557bb03ecf2963936))
