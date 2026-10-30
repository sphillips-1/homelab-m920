locals {
  application_hostnames = {
    bambustudio    = "bambu.${var.zone_name}"
    audiobookshelf = "audiobooks.${var.zone_name}"
    calibre_web    = "books.${var.zone_name}"
    readest        = "readest.${var.zone_name}"
    status         = "status.${var.zone_name}"
    qbittorrent    = "torrents.${var.zone_name}"
  }
}
