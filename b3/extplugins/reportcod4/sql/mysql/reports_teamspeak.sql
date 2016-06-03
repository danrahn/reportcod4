CREATE TABLE IF NOT EXISTS `reports_teamspeak` (
  `id` INT(10) UNSIGNED NOT NULL AUTO_INCREMENT,
  `ts_id` INT(10) NOT NULL DEFAULT 0,
  `nick` VARCHAR(32) NOT NULL DEFAULT 0,
  `time` INT(10) NOT NULL DEFAULT 0,
  PRIMARY KEY (ts_id),
  UNIQUE KEY `ts_id` (`ts_id`),
  KEY `nick` (`nick`),
  KEY `id` (`id`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8