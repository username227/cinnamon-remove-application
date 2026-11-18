# Maintainer: username227 [gfrank227 [at] gmail [dot] com]
pkgname=cinnamon-remove-application
pkgver=0.1.6
pkgrel=1
pkgdesc='Native Cinnamon Uninstall menu handler for Arch using pacman'
arch=('any')
url='https://github.com/username227/cinnamon-remove-application'
license=('GPL-2.0-or-later')
depends=('cinnamon' 'python' 'python-gobject' 'gtk3' 'polkit' 'pacman')
optdepends=('flatpak: Flatpak uninstall support' 'mint-translations: dialog translations')
source=("${pkgname}-v${pkgver}.tar.gz::https://github.com/username227/cinnamon-remove-application/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('71cc8d06e446830dd978b589db6eafd137114f9939230274264fceb936222c3e')

package() {
  install -Dm755 "$srcdir/$pkgname-${pkgver}/usr/bin/cinnamon-remove-application" -t "$pkgdir/usr/bin/"
  install -Dm644 "$srcdir/$pkgname-${pkgver}/usr/lib/cinnamon-remove-application/operations.py" "$pkgdir/usr/lib/cinnamon-remove-application/operations.py"
  install -Dm644 "$srcdir/$pkgname-${pkgver}/usr/lib/cinnamon-remove-application/appearance.py" "$pkgdir/usr/lib/cinnamon-remove-application/appearance.py"
}
