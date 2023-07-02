class MediaMetadata:
    __slots__ = ('_full_info',
                 'id',
                 'title',
                 'formats',
                 'thumbnails',
                 'description',
                 'upload_date',
                 'uploader',
                 'uploader_id',
                 'uploader_url',
                 'channel_id',
                 'channel_url',
                 'duration',
                 'view_count',
                 'average_rating',
                 'age_limit',
                 'webpage_url',
                 'categories',
                 'tags',
                 'playable_in_embed',
                 'is_live',
                 'was_live',
                 'live_status',
                 'release_timestamp',
                 'automatic_captions',
                 'subtitles',
                 'chapters',
                 'like_count',
                 'dislike_count',
                 'channel',
                 'track',
                 'artist',
                 'album',
                 'creator',
                 'alt_title',
                 'availability',
                 'original_url',
                 'webpage_url_basename',
                 'extractor',
                 'extractor_key',
                 'playlist',
                 'playlist_index',
                 'thumbnail',
                 'display_id',
                 'requested_subtitles',
                 'has_drm',
                 'requested_formats',
                 'format',
                 'format_id',
                 'ext',
                 'width',
                 'height',
                 'resolution',
                 'fps',
                 'vcodec',
                 'vbr',
                 'stretched_ratio',
                 'acodec',
                 'abr',
                 'url'
                 )

    SUPPORTED_FILE_TYPES = [
        '3gp', 'aa', 'aac', 'aax', 'act', 'aiff', 'alac', 'amr', 'ape', 'au',
        'awb',
        'dss',
        'dvf',
        'flac',
        'gsm',
        'iklax',
        'ivs',
        'm4a',
        'm4b',
        'm4p',
        'mmf',
        'movpkg',
        'mp3',
        'mpc',
        'msv',
        'nmf',
        'ogg',
        'oga',
        'mogg',
        'opus',
        'ra',
        'rm',
        'raw',
        'rf64',
        'sln',
        'tta',
        'voc',
        'vox',
        'wav',
        'wma',
        'wv',
        'webm',
        '8svx',
        'cda',
        'webm',
        'mkv',
        'flv',
        'vob',
        'ogv',
        'ogg',
        'drc',
        'gifv',
        'webm', 'mpg',
        'mp2',
        'mpeg', 'mpe', 'mpv',
        'ogg', 'mp4', 'm4p', 'm4v'
        'avi', 'wmv',
        'mov', 'qt'
        'flv', 'swf'
        'avchd',
        'mts', 'm2ts', 'ts',
        'yuv',
        'rmvb',
        'viv',
        'amv'
    ]

    def __init__(self, info_dict: dict):
        '''
        Keeps track of the metadata of a YouTube video for ease of access.
        :param info_dict: The dictionary containing the metadata of the video
        '''
        self._full_info = info_dict
        for key in self.__slots__:
            self.__setattr__(key, info_dict[key] if key in info_dict else None)

    @classmethod
    def from_title(cls, title: str, url: str):
        return cls({'title': title, 'ext':'mp3', 'original_url': url, 'duration':0})
    
    @classmethod
    def from_title_extension(cls, title: str, extension: str, url: str, **kwargs):
        base_dict = {'title': title, 'ext': extension, 'original_url': url, 'duration': 0}
        base_dict.update(kwargs)
        return cls(base_dict)

    def __str__(self):
        try:
            return str(self.to_simple_dict())
        except TypeError:
            return "None"

    def __repr__(self):
        try:
            return str(self.to_simple_dict())
        except TypeError:
            return "None"

    def __eq__(self, o):
        if isinstance(o, MediaMetadata):
            if self.id == o.id:
                return True
            else:
                return False
        else:
            return False

    def to_simple_dict(self):
        return {
            'title': self.title,
            'duration': self.duration,
            'url': self.original_url
        }

    def __key(self):
        return (self.id, self.title)       

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        if isinstance(other, MediaMetadata):
            if self.id == other.id and self.title == other.title:
                return True
        return False