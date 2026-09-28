{ pkgs, config, ... }:

let
  root = config.devenv.root;
  notebook = "${root}/apps/notebook";
  # Arduino sketches (the live simulation) are compiled by arduino-cli with the arduino:avr core.
  # The compiler and ctags that core downloads are x86 builds, so on an ARM Mac they come from
  # nixpkgs instead (apps/server/src/Arduino.ts passes these paths as build properties).
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
  packages = [ pkgs.uv pkgs.arduino-cli pkgs.git-lfs ]; # git-lfs: the in-page Arduino compiler (public/arduino/*.wasm)

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

  processes = {
    python-bundle.exec = "node ${notebook}/scripts/bundle-python.mjs --watch";
    notebook.exec = "cd ${notebook} && pnpm exec vite --port 5190 --strictPort";
    notes-server = {
      # the first time: the Arduino core for compiling sketches, and the Servo library (downloaded once)
      exec = "(arduino-cli core list | grep -q arduino:avr || arduino-cli core install arduino:avr); (arduino-cli lib list | grep -q '^Servo ' || arduino-cli lib install Servo); cd ${root}/apps/server && PORT=5191 pnpm dev";
      after = [ "devenv:processes:postgres" ];
    };
  };
}
