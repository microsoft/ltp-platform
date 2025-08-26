package trace

import (
	"context"
	"errors"
	"fmt"
	"log"
	"os"
	"path"

	"github.com/Azure/azure-sdk-for-go/sdk/storage/azblob"

	"AIMiciusModelProxy/types"
)

func handleError(err error) {
	if err != nil {
		log.Println(err.Error())
	}
}

// BlobUploader can upload file to Azure Blob Storage
type BlobUploader struct {
	client        *azblob.Client
	containerName string
	dirPath       string
}

// NewBlobUploader create a new BlobUploader according to the config
func NewBlobUploader(conf *types.AzureStorage) *BlobUploader {
	client, err := azblob.NewClientWithNoCredential(conf.URL, nil)
	handleError(err)
	return &BlobUploader{client: client, containerName: conf.Container, dirPath: conf.Path}
}

// Upload upload the local file to Azure Blob Storage
func (bu *BlobUploader) Upload(localPath string) error {
	// generate blob name
	blobName := fmt.Sprintf("%s/%s", bu.dirPath, path.Base(localPath))
	return uploadFile(bu.client, bu.containerName, localPath, blobName)
}

// uploadFile upload the local file to Azure Blob Storage
func uploadFile(client *azblob.Client, containerName, localPath, remotePath string) error {
	// check whether the localfile is a localFile
	localFile, err := os.Open(localPath)
	handleError(err)
	defer localFile.Close()
	if stat, err := localFile.Stat(); err != nil || stat.IsDir() {
		return errors.New("localPath is not a file")
	}

	// Upload to data to blob storage
	fmt.Printf("Uploading a blob named %s\n", remotePath)
	ctx := context.Background()
	_, err = client.UploadFile(ctx, containerName, remotePath, localFile, nil)
	if err != nil {
		return err
	}
	log.Printf("upload %s to %s successfully\n", localPath, remotePath)

	// TODO: check whether the blob is in the container
	return nil
}
