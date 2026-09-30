{ pkgs, config, ... }:

let
  root = config.devenv.root;
  notebook = "${root}/apps/notebook";
  # the Raspberry Pi Pico's Arduino core (earlephilhower's arduino-pico): its board index
  picoCore = "https://github.com/earlephilhower/arduino-pico/releases/download/global/package_rp2040_index.json";
  # Sketches are compiled in the page (apps/notebook/src/features/simulation/compiler/); arduino-cli, with
  # the arduino:avr and rp2040:rp2040 cores and the libraries, only builds what that compiler links in
  # (apps/notebook/scripts/make-*-sysroot.sh) and the tests' fixtures (make-arduino-fixtures.sh): run
  # arduino-setup once. The compiler and ctags the AVR core downloads are x86 builds, so on an ARM Mac
  # they come from nixpkgs instead (the scripts pass these paths as build properties).
  avr = pkgs.pkgsCross.avr.buildPackages;
  avrToolchain = pkgs.symlinkJoin {
    name = "avr-toolchain";
    paths = [
      avr.gcc
      avr.binutils
      (pkgs.writeShellScriptBin "avr-gcc-ar" ''PATH=${avr.binutils}/bin:$PATH exec ${avr.gcc.cc}/bin/avr-gcc-ar "$@"'')
    ];
  };
in
{
  packages = [ pkgs.uv pkgs.arduino-cli pkgs.git-lfs pkgs.ruff ]; # git-lfs: the in-page Arduino compiler (public/arduino/*.wasm, pico.tar)

  env = pkgs.lib.optionalAttrs (pkgs.stdenv.isDarwin && pkgs.stdenv.isAarch64) {
    ARDUINO_COMPILER_PATH = "${avrToolchain}/bin/";
    ARDUINO_CTAGS_PATH = "${pkgs.universal-ctags}/bin";
  };

  languages.python = {
    enable = true;
    package = pkgs.python3.withPackages (p: [
      p.sympy
      p.pytest
    ]);
  };

  languages.javascript = {
    enable = true;
    directory = ".";
    pnpm = {
      enable = true;
      install.enable = true;
    };
  };

  enterShell = ''
    export PYTHONPATH="${root}/packages/electro/src:${root}/packages/electro-schematic/src:${root}/packages/electro-render/src:${root}/packages/electro-notes/src:${root}/apps/notebook/python''${PYTHONPATH:+:$PYTHONPATH}"
  '';

  services.postgres = {
    enable = true;
    listen_addresses = "127.0.0.1";
    port = 5192;
    initialDatabases = [
      {
        name = "electro";
        user = "postgres";
        pass = "postgres";
      }
    ];
  };

  dotenv.enable = true;

  # installed into .git/hooks on entering the shell: conventional commit messages, and the code formatted and
  # linted as it is committed (Biome for JS/TS/JSON/CSS: biome.json, the version in package.json; ruff for
  # Python: pyproject.toml)
  git-hooks.hooks = {
    convco.enable = true;
    biome = {
      enable = true;
      name = "biome";
      entry = "pnpm exec biome check --write --no-errors-on-unmatched --files-ignore-unknown=true";
      types_or = [ "javascript" "jsx" "ts" "tsx" "json" "css" ];
    };
    ruff.enable = true;
    ruff-format.enable = true;
  };

  # the Arduino cores and the libraries the notebook offers (downloaded once), for the scripts above
  scripts.arduino-setup.exec = "(arduino-cli core list | grep -q arduino:avr || arduino-cli core install arduino:avr); (arduino-cli lib list | grep -q '^Servo ' || arduino-cli lib install Servo); (arduino-cli lib list | grep -q '^LiquidCrystal ' || arduino-cli lib install LiquidCrystal); (arduino-cli lib list | grep -q '^RTClib ' || arduino-cli lib install 'LiquidCrystal I2C' 'Adafruit SSD1306' RTClib); (arduino-cli lib list | grep -q '^Adafruit ILI9341 ' || arduino-cli lib install 'Adafruit ILI9341'); (arduino-cli core list | grep -q rp2040:rp2040 || (arduino-cli core update-index --additional-urls ${picoCore} && arduino-cli core install rp2040:rp2040 --additional-urls ${picoCore}))";

  processes = {
    python-bundle.exec = "node ${notebook}/scripts/bundle-python.mjs --watch";
    notebook.exec = "cd ${notebook} && pnpm exec vite --port 5190 --strictPort";
    notes-server = {
      exec = "cd ${root}/apps/server && PORT=5191 pnpm dev";
      after = [ "devenv:processes:postgres" ];
    };
  };
}
