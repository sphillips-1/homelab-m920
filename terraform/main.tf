locals {
  application_hostnames = {
    local_ai       = "ai.${var.zone_name}"
    bambustudio    = "bambu.${var.zone_name}"
    audiobookshelf = "audiobooks.${var.zone_name}"
    calibre_web    = "books.${var.zone_name}"
    readest        = "readest.${var.zone_name}"
    status         = "status.${var.zone_name}"
    qbittorrent    = "torrents.${var.zone_name}"
  }
}
