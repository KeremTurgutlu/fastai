from ..torch_core import *
from ..basic_data import *
from ..basic_train import *
from .image import *
from ..train import Interpretation
from textwrap import wrap

__all__ = ['SegmentationInterpretation', 'ObjectDetectionInterpretation', 'MultiLabelClassificationInterpretation']

class SegmentationInterpretation(Interpretation):
    "Interpretation methods for classification models."
    def __init__(self, learn:Learner, probs:Tensor, y_true:Tensor, losses:Tensor,
                 ds_type:DatasetType=DatasetType.Valid):
        super(SegmentationInterpretation, self).__init__(learn,probs,y_true,losses,ds_type)
        self.pred_class = self.probs.argmax(dim=1)
        self.c2i = {c:i for i,c in enumerate(self.data.classes)}
        self.i2c = {i:c for c,i in self.c2i.items()}
    
    def top_losses(self, sizes:Tuple, k:int=None, largest=True):
        "Reduce flatten loss to give a single loss value for each image"
        losses = self.losses.view(-1, np.prod(sizes)).mean(-1)
        return losses.topk(ifnone(k, len(losses)), largest=largest)
    
    def _interp_show(self, ims:ImageSegment, classes:Collection=None, sz:int=20, cmap='tab20',
                    title_suffix:str=None):
        fig,axes=plt.subplots(1,2,figsize=(sz,sz))
        np_im = to_np(ims.data).copy()
        # tab20 - qualitative colormaps support max of 20 distinc colors
        # if len(classes) > 20 close idxs map to same color
        # image
        if classes is not None:
            class_idxs = [self.c2i[c] for c in classes]
            mask = np.max(np.stack([np_im==i for i in class_idxs]),axis=0)
            np_im = (np_im*mask).astype(np.float)
            np_im[np.where(mask==0)] = np.nan
        im=axes[0].imshow(np_im[0], cmap=cmap)

        # labels
        np_im_labels = list(np.unique(np_im[~np.isnan(np_im)]))
        c = len(np_im_labels); n = math.ceil(np.sqrt(c))
        label_im = np.array(np_im_labels + [np.nan]*(n**2-c)).reshape(n,n)
        axes[1].imshow(label_im, cmap=cmap)
        for i,l in enumerate([self.i2c[l] for l in np_im_labels]):
            div,mod=divmod(i,n)
            l = "\n".join(wrap(l,10)) if len(l) > 10 else l
            axes[1].text(mod, div, f"{l}", ha='center', color='white', fontdict={'size':sz})

        if title_suffix:
            axes[0].set_title(f"{title_suffix}_imsegment")
            axes[1].set_title(f"{title_suffix}_labels")

    def show_xyz(self, i, classes=None, sz=10):
        'show (image, true and pred) from dataset with color mappings'
        x,y = self.ds[i]
        self.ds.show_xys([x],[y], figsize=(sz/2,sz/2))
        self._interp_show(ImageSegment(self.y_true[i]), classes, sz=sz, title_suffix='true')
        self._interp_show(ImageSegment(self.pred_class[i][None,:]), classes, sz=sz, title_suffix='pred')

    def _generate_confusion(self):
        "Average and Per Image Confusion: intersection of pixels given a true label, true label sums to 1"
        single_img_confusion = []
        mean_confusion = []
        n =  self.pred_class.shape[0]
        for c_j in range(self.data.c):
            true_binary = self.y_true.squeeze(1) == c_j
            total_true = true_binary.view(n,-1).sum(dim=1).float()
            for c_i in range(self.data.c):
                pred_binary = self.pred_class == c_i
                total_intersect = (true_binary*pred_binary).view(n,-1).sum(dim=1).float()
                p_given_t = (total_intersect / (total_true))
                p_given_t_mean = p_given_t[~torch.isnan(p_given_t)].mean()
                single_img_confusion.append(p_given_t)
                mean_confusion.append(p_given_t_mean)
        self.single_img_cm = to_np(torch.stack(single_img_confusion).permute(1,0).view(-1, self.data.c, self.data.c))
        self.mean_cm = to_np(torch.tensor(mean_confusion).view(self.data.c, self.data.c))
        return self.mean_cm, self.single_img_cm

    def _plot_intersect_cm(self, cm, title="Intersection with Predict given True"):
        from IPython.display import display, HTML
        fig,ax=plt.subplots(1,1,figsize=(10,10))
        im=ax.imshow(cm, cmap="Blues")
        ax.set_xlabel("Predicted")
        ax.set_ylabel("True")
        ax.set_title(f"{title}")
        ax.set_xticks(range(self.data.c))
        ax.set_yticks(range(self.data.c))
        ax.set_xticklabels(self.data.classes, rotation='vertical')
        ax.set_yticklabels(self.data.classes)
        fig.colorbar(im)
        
        df = (pd.DataFrame([self.data.classes, cm.diagonal()], index=['label', 'score'])
            .T.sort_values('score', ascending=False))
        with pd.option_context('display.max_colwidth', -1):
            display(HTML(df.to_html(index=False)))
        return df



class ObjectDetectionInterpretation(Interpretation):
    "Interpretation methods for classification models."
    def __init__(self, learn:Learner, probs:Tensor, y_true:Tensor, losses:Tensor, ds_type:DatasetType=DatasetType.Valid):
        raise NotImplementedError
        super(ObjectDetectionInterpretation, self).__init__(learn,probs,y_true,losses,ds_type)
        

class MultiLabelClassificationInterpretation(Interpretation):
    "Interpretation methods for classification models."
    def __init__(self, learn:Learner, probs:Tensor, y_true:Tensor, losses:Tensor, ds_type:DatasetType=DatasetType.Valid,
                     sigmoid:bool=True, thresh:float=0.3):
        raise NotImplementedError
        super(MultiLabelClassificationInterpretation, self).__init__(learn,probs,y_true,losses,ds_type)
        self.pred_class = self.preds.sigmoid(dim=1)>thresh if sigmoid else self.preds>thresh