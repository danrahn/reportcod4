CREATE TABLE IF NOT EXISTS `reports` (
  `id`       INT(10) UNSIGNED NOT NULL AUTO_INCREMENT,
  `reporter` INT(10)      NOT NULL DEFAULT 0,
  `reportee` INT(10)      NOT NULL DEFAULT 0,
  `reason` VARCHAR(64) NOT NULL DEFAULT '',
  `times_reported` INT(10) NOT NULL DEFAULT 0,
  `time` INT(10) NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  UNIQUE KEY `report` (`reporter`, `reportee`),
  KEY `reportee` (`reportee`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;