import random
import os
import argparse
import soundfile as sf
import pandas as pd
import numpy as np
import glob
import pyloudnorm as pyln
import warnings

# Some parameters
eps = 1e-10
max_amp = 0.9

# We wil need to catch a user warning and deal with it
warnings.filterwarnings("error")

random.seed(123)

parser = argparse.ArgumentParser()
parser.add_argument('--storage_dir', type=str, default=None,
                    help='Directory where Librispeech has been downloaded')
parser.add_argument('--dataset_name', type=str, default=None,
                    help='Name of the directory where the dataset will '
                         ' be created')
parser.add_argument('--n_src', type=int, default=2,
                    help='Number of sources desired to create the mixture')


def main(arguments):
    storage_dir = arguments.storage_dir
    storage_dir = 'D://'
    dataset_name = arguments.dataset_name
    dataset_name = 'libri2mix'
    n_src = arguments.n_src
    n_src = 2
    # Check if the LibriSpeech metadata already exist
    try:
        create_librispeech_metadata(storage_dir)
    except FileExistsError:
        pass
    create_dataset_metadata(storage_dir, dataset_name, n_src)


def create_librispeech_metadata(storage_dir):
    """ Generate metadata corresponding to downloaded data in LibriSpeech """

    # Get speakers metadata
    speakers_metadata = create_speakers_dataframe(storage_dir)
    # Go to LibriSpeech root directory
    librispeech_root_path = os.path.join(storage_dir, "LibriSpeech")
    # Create metadata directory
    os.makedirs(os.path.join(librispeech_root_path, 'metadata'), exist_ok=True)
    metadata_directory_path = os.path.join(librispeech_root_path, 'metadata')
    # If it already exists then check the already generated files
    already_generated_csv = os.listdir(metadata_directory_path)
    # Save the already generated files names
    already_generated_csv = [already_generated.strip('.csv')
                             for already_generated in already_generated_csv]
    # Possible directories in the original LibriSpeech
    original_librispeech_directories = ['dev-clean', 'dev-other', 'test-clean',
                                        'test-other', 'train-clean-100',
                                        'train-clean-360', 'train-other-500']
    # Actual directories extracted in your LibriSpeech version
    actual_librispeech_directories = \
        (set(next(os.walk(librispeech_root_path))[1]) &
         set(original_librispeech_directories))
    # Actual directories that haven't already been processed
    not_already_processed_directories = list(
        set(actual_librispeech_directories) - set(already_generated_csv))

    # Go through each directory and create associated metadata
    for directory in not_already_processed_directories:
        # Generate the dataframe relative to the directory
        directory_metadata = create_librispeech_dataframe(
            librispeech_root_path, directory, speakers_metadata)
        # Filter out files that are shorter than 3s
        directory_metadata = directory_metadata[
            directory_metadata['Length'] >= 3*16000]
        # Sort the dataframe according to ascending Length
        directory_metadata = directory_metadata.sort_values('Length')
        # Write the dataframe in a .csv in the metadata directory
        save_path = os.path.join(metadata_directory_path, directory + '.csv')
        directory_metadata.to_csv(save_path, index=False)


def create_speakers_dataframe(storage_dir):
    """ Read metadata from the LibriSpeech dataset and collect infos
    about the speakers """

    print("Reading speakers metadata")
    # Go to LibriSpeech root directory
    librispeech_root_path = os.path.join(storage_dir, 'LibriSpeech')

    # Read SPEAKERS.TXT and create a dataframe
    speakers_metadata_path = os.path.join(librispeech_root_path,
                                          'SPEAKERS.TXT')
    speakers_metadata = pd.read_csv(speakers_metadata_path, sep="|",
                                    skiprows=11,
                                    error_bad_lines=False, header=0,
                                    names=['Speaker_ID', 'Sex', 'Subset',
                                           'MINUTES', 'NAMES'],
                                    skipinitialspace=True)

    speakers_metadata = speakers_metadata.drop(['MINUTES', 'NAMES'],
                                               axis=1)
    # Delete white space
    for column in ['Sex', 'Subset']:
        speakers_metadata[column] = speakers_metadata[column].str.strip()

    # There is a problem with Speaker_ID = 60 his name contains " | " which is
    # the sperator character... Need to handle this case separately

    speakers_metadata.loc[len(speakers_metadata)] = [60, 'M',
                                                     'train-clean-100']

    return speakers_metadata


def create_librispeech_dataframe(librispeech_root_path, directory,
                                 speakers_metadata):
    """ Generate a dataframe that gather infos about the sound files in a
    LibriSpeech subdirectory """

    print(f"Creating {directory} metadata file in LibriSpeech/metadata")
    # Get the current directory path
    directory_path = os.path.join(librispeech_root_path, directory)
    # Look for .flac files in every subdirectories in the current
    # directory
    sound_paths = glob.glob(os.path.join(directory_path, '**/*.flac'),
                            recursive=True)
    # Create the dataframe corresponding to this directory
    directory_metadata = pd.DataFrame(
        columns=['Speaker_ID', 'Sex', 'Subset', 'Length', 'Origin_Path'])

    # Go through the sound file list
    for sound_path in sound_paths:
        # Get the sound file relative path
        relative_path = os.path.relpath(sound_path, librispeech_root_path)
        # Get the sound file name
        sound_name = os.path.split(sound_path)[1]
        # Get its length
        length = len(sf.SoundFile(sound_path))
        # Get the ID of the speaker
        speaker_ID = sound_name.split('-')[0]
        # Find the Sex according to the speaker ID in the LibriSpeech
        # metadata
        sex = speakers_metadata[
            speakers_metadata['Speaker_ID'] == int(speaker_ID)].iat[0, 1]
        # Find the subset according to the speaker ID in the LibriSpeech
        # metadata
        subset = speakers_metadata[
            speakers_metadata['Speaker_ID'] == int(speaker_ID)].iat[0, 2]
        # Add information to the dataframe
        directory_metadata.loc[len(directory_metadata)] = \
            [speaker_ID, sex, subset, length, relative_path]

    return directory_metadata


def create_dataset_metadata(storage_dir, dataset_name, n_src):
    """ Generate metadata for the dataset according to the LibriSpeech
    metadata """

    # Create dataset directory
    os.makedirs(os.path.join(storage_dir, dataset_name), exist_ok=True)
    dataset_directory_path = os.path.join(storage_dir, dataset_name)
    # Create metadata directory
    os.mkdir(os.path.join(dataset_directory_path, 'metadata'))
    mixtures_metadata_directory_path = os.path.join(dataset_directory_path,
                                                    'metadata')
    # Path to Librispeech metadata directory
    librispeech_metadata_directory_path = os.path.join(storage_dir,
                                                       'LibriSpeech/metadata')
    # List metadata files in LibriSpeech
    metadata_file_names = os.listdir(librispeech_metadata_directory_path)
    # If you wish to ignore some metadata files add their name here
    to_be_ignored = ['dev-other.csv']
    for element in to_be_ignored:
        metadata_file_names.remove(element)

    # Go throw each metadata file and create mixture metadata accordingly
    for metadata_file_name in metadata_file_names:
        print(f"Creating {metadata_file_name} "
              f"metadata file in {dataset_name}/metadata")

        # Get the current metadata  file path
        metadata_file_path = os.path.join(librispeech_metadata_directory_path,
                                          metadata_file_name)
        # Open .csv files from LibriSpeech
        metadata_file = pd.read_csv(metadata_file_path)
        # Create dataframe
        metadata_mixtures_file = create_dataset_dataframe(metadata_file, n_src,
                                                          storage_dir)
        # Write the dataframe in a .csv in the metadata directory
        save_path = os.path.join(mixtures_metadata_directory_path,
                                 metadata_file_name)
        metadata_mixtures_file.to_csv(save_path, index=False)


def create_dataset_dataframe(metadata_file, n_src, storage_dir):
    """ Generate dataset dataframe from a LibriSpeech metadata file """

    # Create the dataframe corresponding to a LibriSpeech metadata file
    metadata_mixtures_file = pd.DataFrame(
        columns=['Mixture_ID', 'Speaker_ID_list',
                 'Sex_list', 'Path_list', 'Length_list',
                 'original_loudness_list', 'target_loudness_list', 'Snr_list'])

    # Generate pairs of sources to mix
    pairs = set_pairs(metadata_file, n_src)

    # For each combination create a new line in the dataframe
    for pair in pairs:
        # row is a list containing all the data for this row in the dataframe
        # Add infos, generate sources
        row, sources_list_max, min_length, max_length = \
            add_sources_info_and_read_sources(metadata_file, pair,
                                              n_src, storage_dir)
        # Add infos, randomize loudness and normalize sources
        row, target_loudness_max_list, sources_list_max_norm = \
            compute_and_randomize_loudness(row, sources_list_max, n_src,
                                           max_amp)
        # Do the mixture
        mixture_min, mixture_max = mix(sources_list_max_norm, min_length,
                                       max_length, n_src)
        # Check the mixture for clipping and renormalize if necessary
        row, mixture_min, sources_list_max_norm = \
            check_for_cliping_and_renormalize(row, mixture_max, mixture_min,
                                              sources_list_max_norm, max_amp,
                                              n_src)
        # Compute SNR for the min mode
        row = compute_snr(row, mixture_min, sources_list_max_norm, min_length,
                          n_src, eps)

        # Add information to the dataframe
        metadata_mixtures_file.loc[len(metadata_mixtures_file)] = row

    return metadata_mixtures_file


def set_pairs(metadata_file, n_src):
    """ set pairs of sources to make the mixture """

    # Initialize list for pairs sources
    L = []
    # A counter
    c = 0
    # Index of the rows in the metadata file
    index = list(range(len(metadata_file)))

    # Try to create pairs with different speakers end after 200 fails
    while len(index) >= n_src and c < 200:
        couple = random.sample(index, n_src)
        # Verify that speakers are different
        speaker_list = set([metadata_file.iloc[couple[i]]['Speaker_ID']
                            for i in range(n_src)])
        # If there are duplicates then increment the counter
        if len(speaker_list) != n_src:
            c += 1
        # Else append the combination to L and erase the combination
        # from the available indexes
        else:
            for i in range(n_src):
                index.remove(couple[i])
            L.append(couple)
            c = 0
    return L


def add_sources_info_and_read_sources(metadata_file, pair, n_src,
                                      storage_dir):
    # Get LibriSpeech root directory to be able to read the sources
    librispeech_root_directory_path = os.path.join(storage_dir, 'LibriSpeech')

    # Initialize lists that will be added to the dataframe
    mixtures_id = ""
    speaker_id_list = []
    sex_list = []
    length_list = []
    path_list = []
    # Get sources info
    for i in range(n_src):
        source = metadata_file.iloc[pair[i]]
        speaker_id_list.append(source['Speaker_ID'])
        sex_list.append(source['Sex'])
        length_list.append(source['Length'])
        path_list.append(source['Origin_Path'])
        mixtures_id += os.path.split(
            source['Origin_Path'])[1].strip('.flac') + '_'
    # Just remove the last '_' from mixture_id
    mixtures_id = mixtures_id[:-1]

    # Get the longest and shortest source len
    min_length = min(length_list)
    max_length = max(length_list)
    sources_list_max = []

    # Read the source and compute some info
    for i in range(n_src):
        source = metadata_file.iloc[pair[i]]
        relative_path = source['Origin_Path']
        absolute_path = os.path.join(librispeech_root_directory_path,
                                     relative_path)
        s, _ = sf.read(absolute_path, dtype='float32')
        s_max = np.pad(s, (0, max_length - len(s)))
        sources_list_max.append(s_max)

    # Append to the list
    row = [mixtures_id, speaker_id_list, sex_list, path_list, length_list]

    return row, sources_list_max, min_length, max_length


def compute_and_randomize_loudness(row, sources_list_max, n_src, max_amp):
    """ Compute original loudness and normalise them randomly """

    # Initialize loudness
    loudness_list_max = []
    # In LibriSpeech all sources are at 16KHz hence the meter
    meter = pyln.Meter(16000)
    # Randomize sources loudness
    target_loudness_max_list = []
    sources_list_max_norm = []

    # Normalize loudness
    for i in range(n_src):

        # Compute initial loudness
        loudness_list_max.append(
            meter.integrated_loudness(sources_list_max[i]))
        # Pick a random loudness
        target_loudness = random.uniform(-30, -20)

        try:
            # Normalize loudness
            sources_list_max_norm.append(pyln.normalize.loudness
                                         (sources_list_max[i],
                                          loudness_list_max[i],
                                          target_loudness))
            # Save the loudness
            target_loudness_max_list.append(target_loudness)
        # Catch user warning and normalize file to max amp
        except UserWarning:
            # Normalize to max amp
            sources_list_max_norm.append(
                sources_list_max[i] * max_amp / np.max(np.abs(
                    sources_list_max[i])))
            # Save loudness
            target_loudness_max_list.append(
                meter.integrated_loudness(sources_list_max_norm[i]))

    # Add to row
    row += [loudness_list_max, target_loudness_max_list]

    return row, target_loudness_max_list, sources_list_max_norm


def mix(sources_list_max_norm, min_length, max_length, n_src):
    """ Do the mixture for min mode and max mode """
    # Initialize mixture
    mixture_max = np.zeros(max_length)

    # Do the mixture
    for i in range(n_src):
        mixture_max += sources_list_max_norm[i]
    mixture_min = mixture_max[:min_length]

    return mixture_min, mixture_max


def check_for_cliping_and_renormalize(row, mixture_max, mixture_min,
                                      sources_list_max_norm, max_amp, n_src):
    """ Check the mixture (mode max) for clipping and re normalize accordingly
    """
    # Initialize renormalized sources and loudness
    renormalize_loudness = []
    renormalize_sources = []
    # Recreate the meter
    meter = pyln.Meter(16000)
    # Check for clipping in mixtures
    if np.max(np.abs(mixture_max)) > max_amp:
        weight = max_amp / np.max(np.abs(mixture_max))

    else:
        weight = 1

    # Renormalize
    for i in range(n_src):
        renormalize_sources.append(sources_list_max_norm[i] * weight)
        renormalize_loudness.append(
            meter.integrated_loudness(renormalize_sources[i]))
    mixture_min_renormalize = mixture_min * weight

    # Update the target loudness
    row[-1] = renormalize_loudness
    return row, mixture_min_renormalize, renormalize_sources


def compute_snr(row, mixture_min, sources_list, min_length, n_src,
                eps):
    """Compute the SNR on the mixture mode min"""
    snr_list_min = []

    # Compute SNR for min mode
    for i in range(n_src):
        noise_min = mixture_min - sources_list[i][:min_length]
        snr_list_min.append(10 * np.log10(
            np.mean(np.square(sources_list[i][:min_length]))
            / (np.mean(np.square(noise_min)) + eps) + eps))

    # Add to row
    row.append(snr_list_min)
    return row


if __name__ == "__main__":
    args = parser.parse_args()
    main(args)