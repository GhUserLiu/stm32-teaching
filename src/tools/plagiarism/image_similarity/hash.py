# -*- coding: utf-8 -*-
"""
图片哈希计算器
Image Hash Calculator

计算各种类型的图片哈希值
"""

from typing import Tuple
from enum import Enum
from PIL import Image
import numpy as np


class HashType(Enum):
    """哈希类型"""
    AHASH = 'ahash'      # 平均哈希
    DHASH = 'dhash'      # 差值哈希
    PHASH = 'phash'      # 感知哈希


class ImageHasher:
    """图片哈希计算器"""

    @staticmethod
    def ahash(image: Image.Image, hash_size: int = 8) -> str:
        """
        计算平均哈希

        Args:
            image: PIL图片对象
            hash_size: 哈希大小

        Returns:
            哈希字符串
        """
        # 转换为灰度图
        image = image.convert('L').resize((hash_size, hash_size), Image.LANCZOS)

        # 计算平均值
        pixels = np.array(image).flatten()
        avg = pixels.mean()

        # 生成哈希
        hash_bits = (pixels > avg).astype(int)
        hash_str = ''.join(str(bit) for bit in hash_bits)

        return hash_str

    @staticmethod
    def dhash(image: Image.Image, hash_size: int = 8) -> str:
        """
        计算差值哈希

        Args:
            image: PIL图片对象
            hash_size: 哈希大小

        Returns:
            哈希字符串
        """
        # 转换为灰度图并调整大小（宽度+1）
        image = image.convert('L').resize((hash_size + 1, hash_size), Image.LANCZOS)

        # 计算相邻像素差值
        pixels = np.array(image)
        diff = pixels[:, 1:] > pixels[:, :-1]

        # 生成哈希
        hash_bits = diff.flatten().astype(int)
        hash_str = ''.join(str(bit) for bit in hash_bits)

        return hash_str

    @staticmethod
    def phash(image: Image.Image, hash_size: int = 8) -> str:
        """
        计算感知哈希（使用DCT）

        Args:
            image: PIL图片对象
            hash_size: 哈希大小

        Returns:
            哈希字符串
        """
        # 转换为灰度图
        image = image.convert('L').resize((hash_size * 4, hash_size * 4), Image.LANCZOS)

        # 计算DCT
        pixels = np.array(image, dtype=np.float32)
        dct = np.zeros((hash_size * 4, hash_size * 4))

        # 简化的DCT（每8x8块）
        for i in range(0, hash_size * 4, 8):
            for j in range(0, hash_size * 4, 8):
                block = pixels[i:i+8, j:j+8]
                # 简单的DCT近似
                dct_block = np.zeros((8, 8))
                for u in range(8):
                    for v in range(8):
                        sum_val = 0
                        for x in range(8):
                            for y in range(8):
                                sum_val += block[x, y] * np.cos((2*x+1)*u*np.pi/16) * np.cos((2*y+1)*v*np.pi/16)
                        dct_block[u, v] = sum_val / 4
                dct[i:i+8, j:j+8] = dct_block

        # 提取左上8x8低频部分
        low_freq = dct[:hash_size, :hash_size]

        # 计算平均值（不包括DC分量）
        avg = low_freq[1:, 1:].mean()

        # 生成哈希
        hash_bits = (low_freq > avg).flatten().astype(int)
        hash_str = ''.join(str(bit) for bit in hash_bits)

        return hash_str

    @staticmethod
    def hamming_distance(hash1: str, hash2: str) -> int:
        """
        计算汉明距离

        Args:
            hash1: 哈希字符串1
            hash2: 哈希字符串2

        Returns:
            汉明距离
        """
        if len(hash1) != len(hash2):
            raise ValueError("Hash strings must have the same length")

        return sum(c1 != c2 for c1, c2 in zip(hash1, hash2))

    @staticmethod
    def hash_to_similarity(
        hash1: str,
        hash2: str,
        max_distance: int = 64
    ) -> float:
        """
        将汉明距离转换为相似度

        Args:
            hash1: 哈希字符串1
            hash2: 哈希字符串2
            max_distance: 最大可能距离

        Returns:
            相似度 0-1
        """
        distance = ImageHasher.hamming_distance(hash1, hash2)
        similarity = 1 - (distance / max_distance)
        return max(0, similarity)

    @staticmethod
    def calculate_hash(
        image: Image.Image,
        hash_type: HashType = HashType.DHASH
    ) -> str:
        """
        计算指定类型的哈希

        Args:
            image: PIL图片对象
            hash_type: 哈希类型

        Returns:
            哈希字符串
        """
        if hash_type == HashType.AHASH:
            return ImageHasher.ahash(image)
        elif hash_type == HashType.DHASH:
            return ImageHasher.dhash(image)
        elif hash_type == HashType.PHASH:
            return ImageHasher.phash(image)
        else:
            raise ValueError(f"Unsupported hash type: {hash_type}")
