locals {
  application_hostnames = {
    audiobookshelf = "audiobooks.${var.zone_name}"
    calibre_web    = "books.${var.zone_name}"
  }
  audiobookshelf_test_hostname = "audiobooks-access-test.${var.zone_name}"
}
