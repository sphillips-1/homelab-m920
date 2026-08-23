locals {
  application_hostnames = {
    audiobookshelf = "audiobooks.${var.zone_name}"
    calibre_web    = "books.${var.zone_name}"
    status         = "status.${var.zone_name}"
  }
}
