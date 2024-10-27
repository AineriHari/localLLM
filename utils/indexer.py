"""
Module for indexing documents using FAISS with embeddings generated by a sentence transformer model.

This module provides functionality to read documents, convert non-PDF files to PDF format,
and index the documents using FAISS for efficient retrieval. It handles encoding issues when reading
text files and generates embeddings for the documents using a specified sentence transformer model.

Key Functions:
- read_file_with_fallback: Reads a file with fallback encoding handling.
- index_documents: Indexes documents in a specified folder using FAISS.
"""

import os
import traceback
import chardet
import numpy as np
import faiss
import logging
import json
from typing import Tuple, List, Dict
from sentence_transformers import SentenceTransformer


# Set up logging
logging.basicConfig(level=logging.INFO)


def create_filenames_mapping(filenames: List[str]) -> Dict[int, str]:
    """
    Creates a mapping from FAISS index to the actual document filenames.

    Args:
        filenames (List[str]): A list of filenames used to create embeddings.

    Returns:
        Dict[int, str]: A dictionary mapping FAISS indices to filenames.
    """
    filenames_mapping = {}

    for idx, doc_file in enumerate(filenames):
        # Map the FAISS index to the document filename
        filenames_mapping[idx] = doc_file

    return filenames_mapping


def read_file_with_fallback(file_path: str) -> str:
    """
    Reads a file with fallback encoding handling.

    This function attempts to read a file using the detected encoding from the chardet library.
    If it encounters a UnicodeDecodeError, it falls back to a common encoding (latin1).

    Args:
        file_path (str): The path to the file to read.

    Returns:
        str: The contents of the file as a string.
    """
    with open(file_path, 'rb') as file:
        raw_data = file.read()
        detected_encoding = chardet.detect(raw_data)['encoding']
    
    try:
        # Attempt to read the file with the detected encoding
        with open(file_path, 'r', encoding=detected_encoding) as file:
            return file.read()
    except UnicodeDecodeError:
        # Fallback to a common encoding like 'latin1'
        with open(file_path, 'r', encoding='latin1') as file:
            return file.read()


def index_documents(
        folder_path: str,
        index_path: str = None,
        indexer_model: str = 'paraphrase-MiniLM-L6-v2'
) -> faiss.Index:
    """
    Indexes documents in the specified folder using FAISS.

    Args:
        folder_path (str): The path to the folder containing documents to index.
        index_path (str): The path where the index should be saved, including filename.
        indexer_model (str): The name of the sentence transformer model to use.

    Returns:
        Tuple[faiss.Index, dict]: The FAISS index and a dictionary mapping indices to filenames.
    """
    try:
        logging.info(f"Starting document indexing in folder: {folder_path}")

        # Load documents from folder
        docs = []
        filenames = []
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            try:
                # Use the read_file_with_fallback method to handle encoding issues
                content = read_file_with_fallback(file_path)
                docs.append(content)
                # Append filename in the same order as docs
                filenames.append(filename)
            except Exception as e:
                logging.exception(f"Error reading file {filename}: {str(e)}")

        logging.info(f"Loaded {len(docs)} documents")

        logging.info("Initiating embedding and indexing... This may take some time.")
        # Load the pre-trained model for embedding generation
        model = SentenceTransformer(indexer_model)

        # Generate embeddings for each document
        embeddings = model.encode(docs, convert_to_tensor=False)
        embeddings = np.array(embeddings).astype("float32")

        # Create the FAISS index
        index = faiss.IndexFlatL2(embeddings.shape[1])
        index.add(embeddings)

        logging.info(f"Indexing completed. Index saved at '{index_path}'.")

        # Ensure index_path is a file path (not a directory)
        if index_path:
            # If directory path is given, append a filename like 'index.faiss'
            if os.path.isdir(index_path):
                index_faiss_path = os.path.join(index_path, 'index.faiss')
                faiss.write_index(index, index_faiss_path)

            # Create the filenames mapping based on the consistent document order
            filenames_mapping = create_filenames_mapping(filenames)

            # Save filenames mapping to a JSON file
            mapping_path = os.path.abspath(os.path.join(index_path, "faiss_index_file_mapping.json"))
            with open(mapping_path, 'w') as f:
                json.dump(filenames_mapping, f)

        return index
    except Exception as e:
        logging.exception(traceback.format_exc())
        logging.error(f"Error during indexing: {str(e)}")
        raise
