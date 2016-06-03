CREATE TABLE IF NOT EXISTS `reports_banned` (
  `banned_id` INT(10) NOT NULL DEFAULT 0,
  `banner_id` INT(10) NOT NULL DEFAULT 0,
  `reason` VARCHAR(64) NOT NULL DEFAULT '',
  `time` INT(10) NOT NULL DEFAULT 0,
  PRIMARY KEY (banned_id),
  UNIQUE KEY `banned_id` (`banned_id`),
  KEY `banner_id` (`banner_id`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;