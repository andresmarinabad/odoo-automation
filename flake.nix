{
  description = "Entorno Odoo API con UV y Nix";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs { inherit system; };
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            python311
            uv
            pkg-config
          ];

          shellHook = ''
            if [ ! -d ".venv" ]; then
              uv venv
            fi

            source .venv/bin/activate
          '';
        };
      }
    );
}
