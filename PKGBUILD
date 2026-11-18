# Maintainer: username227
# Development test PKGBUILD; not a tagged AUR release.
pkgname=cinnamon-remove-application
pkgver=0.1.2
pkgrel=1
pkgdesc='Native Cinnamon Uninstall menu handler for Arch using pacman'
arch=('any')
url='https://github.com/username227/cinnamon-remove-application'
license=('GPL-2.0-or-later')
depends=('cinnamon' 'python' 'python-gobject' 'gtk3' 'polkit' 'pacman')
makedepends=('git')
optdepends=('flatpak: Flatpak uninstall support' 'mint-translations: dialog translations')
source=("$pkgname::git+$url.git#branch=modernize/cinnamon-6.8-pacman")
sha256sums=('SKIP')

package() {
  install -Dm755 "$srcdir/$pkgname/usr/bin/cinnamon-remove-application" \
    "$pkgdir/usr/bin/cinnamon-remove-application"
  install -Dm644 "$srcdir/$pkgname/usr/lib/cinnamon-remove-application/operations.py" \
    "$pkgdir/usr/lib/cinnamon-remove-application/operations.py"
}

