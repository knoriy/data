import os
import unittest
import warnings

import expecttest

from _utils._common_utils_for_test import create_temp_dir, create_temp_files, reset_after_n_next_calls

from torchdata.datapipes.iter import (
    FileLister,
    Boto3FileLister,
    Boto3FileOpener,
    IterableWrapper,
    IterDataPipe,
)

try:
    import boto3

    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False
skipIfNoBoto3 = unittest.skipIf(not HAS_BOTO3, "no boto3")


class TestDataPipeBoto3(expecttest.TestCase):
    def setUp(self):
        self.temp_dir = create_temp_dir()
        self.temp_files = create_temp_files(self.temp_dir)
        self.temp_sub_dir = create_temp_dir(self.temp_dir.name)
        self.temp_sub_files = create_temp_files(self.temp_sub_dir, 4, False)

        self.temp_dir_2 = create_temp_dir()
        self.temp_files_2 = create_temp_files(self.temp_dir_2)
        self.temp_sub_dir_2 = create_temp_dir(self.temp_dir_2.name)
        self.temp_sub_files_2 = create_temp_files(self.temp_sub_dir_2, 4, False)

    def tearDown(self):
        try:
            self.temp_sub_dir.cleanup()
            self.temp_dir.cleanup()
            self.temp_sub_dir_2.cleanup()
            self.temp_dir_2.cleanup()
        except Exception as e:
            warnings.warn(f"TestDataPipeBoto3 was not able to cleanup temp dir due to {e}")

    def _write_text_files(self):
        def filepath_fn(name: str) -> str:
            return os.path.join(self.temp_dir.name, os.path.basename(name))

        name_to_data = {"1.text": b"DATA", "2.text": b"DATA", "3.text": b"DATA"}
        source_dp = IterableWrapper(sorted(name_to_data.items()))
        saver_dp = source_dp.save_to_disk(filepath_fn=filepath_fn, mode="wb")
        list(saver_dp)

    @skipIfNoBoto3
    def test_boto3_file_lister_iterdatapipe(self):
        datapipe: IterDataPipe = Boto3FileLister(root="file://" + self.temp_sub_dir.name)

        # check all file paths within sub_folder are listed
        for path in datapipe:
            self.assertIn(
                path.split("://")[1],
                {boto3.implementations.local.make_path_posix(file) for file in self.temp_sub_files},
            )

        # checks for functional API
        datapipe = IterableWrapper(["file://" + self.temp_sub_dir.name])
        datapipe = datapipe.list_files_by_boto3()
        for path in datapipe:
            self.assertIn(
                path.split("://")[1],
                {boto3.implementations.local.make_path_posix(file) for file in self.temp_sub_files},
            )

    @skipIfNoBoto3
    def test_boto3_file_lister_iterdatapipe_with_list(self):
        datapipe: IterDataPipe = Boto3FileLister(
            root=["file://" + self.temp_sub_dir.name, "file://" + self.temp_sub_dir_2.name]
        )

        # check all file paths within sub_folder are listed
        file_lister = list(map(lambda path: path.split("://")[1], datapipe))
        file_lister.sort()
        temp_files = list(
            map(
                lambda file: boto3.implementations.local.make_path_posix(file),
                self.temp_sub_files + self.temp_sub_files_2,
            )
        )
        temp_files.sort()

        # check all file paths within sub_folder are listed
        self.assertEqual(file_lister, temp_files)

        # checks for functional API
        datapipe = IterableWrapper(["file://" + self.temp_sub_dir.name, "file://" + self.temp_sub_dir_2.name])
        datapipe = datapipe.list_files_by_boto3()
        res = list(map(lambda path: path.split("://")[1], datapipe))
        res.sort()
        temp_files = list(
            map(
                lambda file: boto3.implementations.local.make_path_posix(file),
                self.temp_sub_files + self.temp_sub_files_2,
            )
        )
        temp_files.sort()
        self.assertEqual(res, temp_files)

    @skipIfNoBoto3
    def test_boto3_file_loader_iterdatapipe(self):
        datapipe1 = Boto3FileLister(root="file://" + self.temp_sub_dir.name)
        datapipe2 = Boto3FileOpener(datapipe1)
        datapipe3 = Boto3FileOpener(datapipe1, kwargs_for_open={"encoding": "cp037"})

        # check contents of file match
        for _, f in datapipe2:
            self.assertEqual(f.read(), "0123456789abcdef")

        # Opened with a different encoding, hence NotEqual
        for _, f in datapipe3:
            self.assertNotEqual(f.read(), "0123456789abcdef")

        # Reset Test: Ensure the resulting streams are still readable after the DataPipe is reset/exhausted
        self._write_text_files()
        lister_dp = FileLister(self.temp_dir.name, "*.text")
        boto3_file_opener_dp = lister_dp.open_files_by_boto2(mode="rb")

        n_elements_before_reset = 2
        res_before_reset, res_after_reset = reset_after_n_next_calls(boto3_file_opener_dp, n_elements_before_reset)
        self.assertEqual(2, len(res_before_reset))
        self.assertEqual(3, len(res_after_reset))
        for _name, stream in res_before_reset:
            self.assertEqual(b"DATA", stream.read())
        for _name, stream in res_after_reset:
            self.assertEqual(b"DATA", stream.read())

    # @skipIfNoBoto3
    # def test_boto3_saver_iterdatapipe(self):
    #     def filepath_fn(name: str) -> str:
    #         return "file://" + os.path.join(self.temp_dir.name, os.path.basename(name))

    #     # Functional Test: Saving some data
    #     name_to_data = {"1.txt": b"DATA1", "2.txt": b"DATA2", "3.txt": b"DATA3"}
    #     source_dp = IterableWrapper(sorted(name_to_data.items()))
    #     saver_dp = source_dp.save_by_boto3(filepath_fn=filepath_fn, mode="wb")
    #     res_file_paths = list(saver_dp)
    #     expected_paths = [filepath_fn(name) for name in name_to_data.keys()]
    #     self.assertEqual(expected_paths, res_file_paths)
    #     for name in name_to_data.keys():
    #         p = filepath_fn(name).split("://")[1]
    #         with open(p) as f:
    #             self.assertEqual(name_to_data[name], f.read().encode())

    #     # Reset Test:
    #     saver_dp = Boto3Saver(source_dp, filepath_fn=filepath_fn, mode="wb")
    #     n_elements_before_reset = 2
    #     res_before_reset, res_after_reset = reset_after_n_next_calls(saver_dp, n_elements_before_reset)
    #     self.assertEqual([filepath_fn("1.txt"), filepath_fn("2.txt")], res_before_reset)
    #     self.assertEqual(expected_paths, res_after_reset)
    #     for name in name_to_data.keys():
    #         p = filepath_fn(name).split("://")[1]
    #         with open(p) as f:
    #             self.assertEqual(name_to_data[name], f.read().encode())

    #     # __len__ Test: returns the length of source DataPipe
    #     self.assertEqual(3, len(saver_dp))

    @skipIfNoBoto3
    def test_boto3_memory_list(self):
        fs = boto3.filesystem("memory")
        fs.mkdir("foo")
        fs.touch("foo/bar1")
        fs.touch("foo/bar2")

        datapipe = Boto3FileLister(root="memory://foo")
        self.assertEqual(set(datapipe), {"memory:///foo/bar1", "memory:///foo/bar2"})

        datapipe = Boto3FileLister(root="memory://foo/bar1")
        self.assertEqual(set(datapipe), {"memory://foo/bar1"})

    @skipIfNoBoto3
    def test_boto3_memory_load(self):
        fs = boto3.filesystem("memory")
        with fs.open("file", "w") as f:
            f.write("hello")
        with fs.open("file2", "w") as f:
            f.write("hello2")

        files = ["memory://file", "memory://file2"]
        datapipe = Boto3FileOpener(files)
        self.assertEqual([f.read() for _, f in datapipe], ["hello", "hello2"])

    # @skipIfNoBoto3
    # def test_boto3_memory_save(self):
    #     def filepath_fn(name: str) -> str:
    #         return "memory://" + name

    #     name_to_data = {"1.txt": b"DATA1", "2.txt": b"DATA2"}
    #     source_dp = IterableWrapper(sorted(name_to_data.items()))
    #     saver_dp = Boto3Saver(source_dp, filepath_fn=filepath_fn, mode="wb")

    #     self.assertEqual(set(saver_dp), {"memory://1.txt", "memory://2.txt"})


if __name__ == "__main__":
    unittest.main()
